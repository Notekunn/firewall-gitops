# Runbook migrate state v2 thủ công

Runbook này dùng để adopt đúng các resource đang được YAML quản lý vào state mới,
không import toàn bộ cấu hình firewall và không dùng apply để tạo lại resource đã
tồn tại. Thực hiện lần lượt `fw-core`, `fw-mgmt`, rồi `fw-out`; chỉ chuyển sang
cluster tiếp theo sau khi cluster hiện tại đã qua toàn bộ checkpoint.

Các script thực thi là nguồn sự thật:

- [`scripts/deploy.sh`](../scripts/deploy.sh): chọn state, tạo plan và apply saved plan.
- [`scripts/import-v2-state.sh`](../scripts/import-v2-state.sh): validate manifest,
  kiểm tra state v2 rỗng, import và tạo plan v2.
- [`scripts/migration_inventory.py`](../scripts/migration_inventory.py): suy ra
  ownership chính xác từ YAML.
- [`scripts/check-plan-json.py`](../scripts/check-plan-json.py): chặn create,
  delete, replace, ownership expansion và thay đổi identity FortiGate policy.

## Nguyên tắc bắt buộc

- Giữ nguyên state v1; không dùng `destroy`, `tofu init -migrate-state` hoặc
  `tofu state push` để tạo state v2.
- Không apply một plan mới sinh trong apply job. Chỉ apply đúng file plan đã review.
- Không tiếp tục nếu import ID không chắc chắn, tên bị trùng, state v2 không rỗng,
  plan chứa create/delete/replace, hoặc inventory unmanaged thay đổi.
- State backup và inventory có thể chứa dữ liệu nhạy cảm. Lưu ngoài repository,
  trong thư mục hạn chế quyền; không commit hoặc đưa chúng vào CI artifacts.
- Credential phải lấy từ secret store đã được tổ chức phê duyệt. Không lưu
  credential trong shell history, manifest, tài liệu hoặc repository.

## 1. Chuẩn bị máy chạy

Chạy từ repository root trên branch chứa thay đổi migration.

Yêu cầu:

- OpenTofu đúng phiên bản `1.12.6`.
- Python có các package trong `requirements.txt`.
- Có quyền đọc/ghi GitLab HTTP state và quyền lock state.
- Có quyền đọc firewall để lấy inventory/import ID.
- Chỉ bật quyền ghi firewall khi đã đến bước apply được duyệt.

Kiểm tra local trước khi truy cập backend:

```bash
tofu version
python3 scripts/validate_yaml.py
tofu fmt -check -recursive

export TF_DATA_DIR="$(mktemp -d)"
tofu -chdir=terraform init -backend=false -lockfile=readonly -input=false
tofu -chdir=terraform validate
unset TF_DATA_DIR
```

Kỳ vọng `tofu version` là `1.12.6`, YAML hợp lệ và OpenTofu validate thành công.

## 2. Nạp credential vào shell hiện tại

Lấy giá trị từ secret store đã được phê duyệt. Các dòng dưới đây chỉ liệt kê tên
biến; không thay credential thật vào tài liệu hoặc commit chúng.

Backend GitLab cần:

```bash
export GITLAB_API_URL="<GitLab API v4 URL>"
export GITLAB_PROJECT_ID="<project ID>"
export GITLAB_USERNAME="<backend username>"
export GITLAB_PASSWORD="<backend token/password from secret store>"

# Các lệnh tofu chạy trực tiếp ngoài deploy.sh cũng cần hai biến này.
export TF_HTTP_USERNAME="$GITLAB_USERNAME"
export TF_HTTP_PASSWORD="$GITLAB_PASSWORD"
```

`fw-core` dùng PAN-OS provider:

```bash
export PANOS_HOSTNAME="<hostname from approved inventory>"
export PANOS_API_KEY="<API key from secret store>"
# Hoặc dùng PANOS_USERNAME và PANOS_PASSWORD theo policy hiện hành.
```

`fw-mgmt` và `fw-out` dùng FortiOS provider 1.26.1:

```bash
export FORTIOS_ACCESS_HOSTNAME="<hostname from approved inventory>"
export FORTIOS_ACCESS_TOKEN="<API token from secret store>"
export FORTIOS_INSECURE="false"
```

Chỉ đặt `FORTIOS_INSECURE=true` khi ngoại lệ TLS đã được phê duyệt. Có thể dùng
`FORTIOS_ACCESS_USERNAME` và `FORTIOS_ACCESS_PASSWORD` thay token nếu đó là cơ
chế được tổ chức cho phép.

## 3. Chọn cluster và thư mục bằng chứng

Lặp lại toàn bộ runbook cho từng cluster theo đúng thứ tự.

```bash
export CLUSTER="fw-core"
case "$CLUSTER" in fw-core|fw-mgmt|fw-out) ;; *) exit 1 ;; esac

# Chọn một thư mục bảo mật, bền vững và nằm ngoài repository.
export MIGRATION_DIR="<restricted external directory>/$CLUSTER"
mkdir -p "$MIGRATION_DIR"
chmod 700 "$MIGRATION_DIR"
umask 077
```

Không dùng `/tmp` làm nơi lưu backup chính thức. Trước khi tiếp tục, freeze apply
cho cluster: không trigger manual apply job, xác nhận không có pipeline/operator
khác đang thay đổi cùng firewall hoặc state.

## 4. Validate riêng cluster

```bash
python3 scripts/validate_yaml.py --cluster "$CLUSTER"
```

Dừng nếu validation thất bại. Không sửa state để né lỗi YAML.

## 5. Backup state v1

Khởi tạo đúng backend v1 và dùng cùng `TF_DATA_DIR` cho lệnh `state pull`:

```bash
export TF_DATA_DIR="$PWD/terraform/.terraform/$CLUSTER-v1"
./scripts/deploy.sh -c "$CLUSTER" -a init --state-generation v1

tofu -chdir=terraform state pull > "$MIGRATION_DIR/state-v1.json"
python3 - "$MIGRATION_DIR/state-v1.json" <<'PY'
import json
import sys

state = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"lineage={state.get('lineage')} serial={state.get('serial')}")
PY
```

Checkpoint:

- File backup parse được dưới dạng JSON.
- `lineage` và `serial` đã được ghi vào change record bảo mật.
- File không nằm trong repository và không được stage bởi Git.

## 6. Export inventory trước migration

Dùng API/export read-only đã được đội firewall phê duyệt. Repository chưa tự động
hóa bước này vì ID và cách export phụ thuộc thiết bị thực tế.

Inventory trước migration phải đủ để so sánh sau apply:

- Tên, ID và loại của address, service và schedule liên quan.
- Toàn bộ tên, ID và thứ tự policy/rule trong phạm vi có thể bị tác động.
- Đánh dấu resource có trong YAML và resource unmanaged.
- Với PAN-OS, ghi lại toàn bộ rule order quanh block YAML-managed; grouped rule
  import không được kéo rule unmanaged vào ownership.
- Với FortiGate, ghi lại `policyid` và thứ tự policy; không suy ID từ vị trí YAML.

Lưu raw export thành `$MIGRATION_DIR/inventory-before.export`; tạo checksum để
phát hiện file bị thay đổi:

```bash
sha256sum "$MIGRATION_DIR/inventory-before.export" \
  > "$MIGRATION_DIR/inventory-before.sha256"
```

Dừng nếu không lấy được ID ổn định hoặc không phân biệt được managed/unmanaged.

## 7. Tạo manifest import

Sinh danh sách địa chỉ OpenTofu dự kiến với cột import ID để trống:

```bash
python3 - "$CLUSTER" > "$MIGRATION_DIR/manifest.tsv" <<'PY'
import sys
from scripts.migration_inventory import ownership

for address in ownership(f"clusters/{sys.argv[1]}"):
    print(f"{address}\t")
PY
```

Điền import ID lấy từ inventory/API vào cột thứ hai. Mỗi dòng phải có đúng hai
cột phân tách bằng một ký tự tab:

```text
<opentofu-resource-address><TAB><provider-import-id>
```

Không thêm header. Có thể thêm comment bắt đầu bằng `#`. Manifest phải chứa mọi
resource YAML-owned đúng một lần và không chứa credential hoặc raw state.

Validate manifest trước khi truy cập state v2:

```bash
python3 scripts/migration_inventory.py \
  --cluster-dir "clusters/$CLUSTER" \
  --manifest "$MIGRATION_DIR/manifest.tsv"
```

Checkpoint review hai người nếu quy trình vận hành yêu cầu:

- Địa chỉ OpenTofu khớp YAML hiện tại.
- Import ID đến từ thiết bị/API, không suy đoán từ display name.
- FortiGate policy manifest giữ đúng `policyid`.
- PAN-OS grouped rule import chỉ đại diện block YAML-managed.

## 8. Import vào state v2

Script sẽ tự dừng nếu manifest không hợp lệ hoặc state v2 đã có resource:

```bash
./scripts/import-v2-state.sh "$CLUSTER" "$MIGRATION_DIR/manifest.tsv"
```

Lệnh này import lần lượt các địa chỉ trong manifest rồi tạo:

- `terraform/plan-$CLUSTER-v2.tfplan`
- `terraform/plan-$CLUSTER-v2.json`

Plan gate phải pass. Nếu import dừng giữa chừng, không chạy lại mù quáng: kiểm tra
`state-list`, đối chiếu những resource đã vào state, rồi quyết định tiếp tục hay
loại bỏ riêng state entry sai sau review. Không xóa resource trên firewall.

## 9. Xác nhận state membership

Tạo hai danh sách đã sort và yêu cầu diff rỗng:

```bash
python3 - "$CLUSTER" > "$MIGRATION_DIR/expected-state.txt" <<'PY'
import sys
from scripts.migration_inventory import ownership

for address in sorted(ownership(f"clusters/{sys.argv[1]}")):
    print(address)
PY

export TF_DATA_DIR="$PWD/terraform/.terraform/$CLUSTER-v2"
./scripts/deploy.sh -c "$CLUSTER" -a init --state-generation v2
tofu -chdir=terraform state list | sort > "$MIGRATION_DIR/actual-state.txt"
diff -u "$MIGRATION_DIR/expected-state.txt" "$MIGRATION_DIR/actual-state.txt"
```

Dừng nếu thiếu/thừa bất kỳ địa chỉ nào.

## 10. Kiểm tra refresh-only

```bash
set +e
tofu -chdir=terraform plan \
  -input=false \
  -refresh-only \
  -detailed-exitcode \
  -var="cluster_name=$CLUSTER" \
  -out="$MIGRATION_DIR/refresh-only.tfplan"
refresh_exit=$?
set -e

case "$refresh_exit" in
  0) echo "Refresh-only: no drift" ;;
  2) echo "Refresh-only: review required" ;;
  *) echo "Refresh-only failed" >&2; exit "$refresh_exit" ;;
esac
```

Exit code `2` không tự động là lỗi, nhưng mọi khác biệt phải được hiểu và reconcile
trong code/YAML/import trước normal plan. Không dùng broad `ignore_changes` để che
provider defaults và không apply refresh-only plan như một shortcut.

## 11. Tạo và review normal saved plan

Tạo lại plan sau khi refresh-only đã được giải thích:

```bash
./scripts/deploy.sh \
  -c "$CLUSTER" \
  -a plan \
  --state-generation v2 \
  --plan-file "plan-$CLUSTER-v2.tfplan"
```

Script tạo JSON và tự chạy ownership/destructive gate. Review thêm bằng:

```bash
tofu -chdir=terraform show "plan-$CLUSTER-v2.tfplan"
python3 scripts/check-plan-json.py \
  "terraform/plan-$CLUSTER-v2.json" \
  --cluster "$CLUSTER"
```

Chỉ duyệt apply khi:

- Không có create, delete hoặc replace.
- Update chỉ tác động resource YAML-owned và đúng nội dung mong đợi.
- Không có rule/member unmanaged trong before hoặc after của bulk resource.
- PAN-OS rule order khớp YAML và không kéo rule lân cận vào ownership.
- FortiGate `policyid` giữ nguyên.
- File `.tfplan` được giữ nguyên từ lúc review đến lúc apply.

Sau khi review xong, ghi checksum của plan được duyệt:

```bash
sha256sum "terraform/plan-$CLUSTER-v2.tfplan" \
  > "$MIGRATION_DIR/reviewed-plan.sha256"
```

## 12. Apply đúng saved plan

Chỉ bật quyền ghi firewall ở thời điểm này và theo change window được duyệt.

```bash
sha256sum -c "$MIGRATION_DIR/reviewed-plan.sha256"

./scripts/deploy.sh \
  -c "$CLUSTER" \
  -a apply \
  --state-generation v2 \
  --plan-file "plan-$CLUSTER-v2.tfplan"
```

`deploy.sh` kiểm tra lại cluster và plan gate trước khi apply. Dừng ngay nếu check
không pass; không tạo plan thay thế trong cửa sổ apply mà chưa review lại.

## 13. Xác nhận sau apply

Export inventory sau apply bằng cùng API, cùng scope và cùng cách sort như before.
So sánh tối thiểu:

- Unmanaged object/rule name và ID không đổi.
- Rule/policy order unmanaged không đổi.
- Resource YAML-owned có đúng thay đổi đã review.
- FortiGate `policyid` không đổi.
- PAN-OS audit history ghi nhận đúng ticket/revision khi có `change` metadata.

Kiểm tra checksum/file và diff bằng công cụ được đội firewall phê duyệt. Không
đưa raw inventory vào repository.

Sau đó chạy plan lần hai:

```bash
./scripts/deploy.sh \
  -c "$CLUSTER" \
  -a plan \
  --state-generation v2 \
  --plan-file "plan-$CLUSTER-v2-post-apply.tfplan"
```

Plan phải báo no changes và JSON gate phải pass. Nếu có recurring diff, giữ freeze
và xử lý nguyên nhân trước khi cutover CI.

## 14. Cutover CI

Trong GitLab, chạy pipeline cho đúng branch/commit với biến:

```text
STATE_GENERATION=v2
```

Review job `plan-$CLUSTER`, sau đó mới trigger manual job `apply-$CLUSTER`. Ba
cluster dùng chung resource group theo cluster, vì vậy không chạy v1 và v2 song
song cho cùng cluster.

Giữ state v1 read-only trong observation window. Ghi change record gồm commit,
cluster, state name `firewall-$CLUSTER-v2`, plan artifact, inventory checksums và
kết quả second plan; không ghi credential hoặc raw state vào record công khai.

## 15. Rollback

Rollback khi có unmanaged delta, sai rule order, sai policy identity, apply lỗi
không hiểu rõ hoặc second plan không converge:

1. Dừng mọi migration cluster tiếp theo và giữ apply freeze.
2. Khôi phục cấu hình thiết bị bằng quy trình backup/restore đã được vendor và
   đội firewall phê duyệt; không dùng `tofu destroy`.
3. Chạy pipeline với `STATE_GENERATION=v1` để quay route CI về v1.
4. Tạo và review plan v1 trước mọi apply; không giả định state v1 đồng nghĩa thiết
   bị đã được phục hồi hoàn toàn.
5. Giữ nguyên state v2 để điều tra. Không copy/push state v1 sang v2 và không xóa
   state v2 khi chưa có quyết định phục hồi riêng.
6. So sánh inventory với bản before và chỉ gỡ freeze khi unmanaged configuration
   đã trở lại đúng trạng thái.

## 16. Kết thúc cluster

Cluster được coi là hoàn tất khi:

- State membership khớp YAML ownership chính xác.
- Normal plan trước apply không chứa hành động ngoài phạm vi.
- Before/after inventory chứng minh unmanaged configuration không đổi.
- Second plan báo no changes.
- CI đã dùng v2 và state v1 vẫn còn khả dụng cho rollback.

Sau observation window được duyệt, chuyển sang cluster kế tiếp. Không tự động rút
ngắn observation window chỉ vì plan hoặc apply thành công.
