# Awesome Dashboard — cho Anki

***Tiếng Việt** · [English](README.md)*

<p>
<a href="https://github.com/kpdo2910/awesome-dashboard/releases/latest"><img alt="Bản mới nhất" src="https://img.shields.io/github/v/release/kpdo2910/awesome-dashboard?style=flat-square&label=release&color=0a84ff"></a>
<a href="https://ankiweb.net/shared/info/1243176816"><img alt="AnkiWeb 1243176816" src="https://img.shields.io/badge/AnkiWeb-1243176816-1ba9c4?style=flat-square"></a>
<img alt="Anki 23.10+" src="https://img.shields.io/badge/Anki-23.10%2B-30d158?style=flat-square">
<img alt="Tiếng Việt, English, Português (Brasil), 日本語" src="https://img.shields.io/badge/VI%20%C2%B7%20EN%20%C2%B7%20PT--BR%20%C2%B7%20JA-ff9f0a?style=flat-square">
<a href="LICENSE"><img alt="Giấy phép MIT" src="https://img.shields.io/badge/gi%E1%BA%A5y%20ph%C3%A9p-MIT-8e8e93?style=flat-square"></a>
</p>

Awesome Dashboard thay màn hình bộ thẻ, màn hình tổng quan và khung màn ôn thẻ
của Anki bằng một giao diện thống nhất: thẻ thống kê, heatmap hoạt động kiểu
GitHub, đồng hồ Pomodoro, theo dõi thói quen, đếm ngược kỳ thi và thanh bên tuỳ
chọn — với sáu chủ đề màu, mỗi chủ đề có bảng màu sáng và tối riêng, hỗ trợ
tiếng Việt, tiếng Anh, tiếng Bồ Đào Nha (Brasil) và tiếng Nhật.

![Awesome Dashboard](docs/images/feature-vi.png)

Yêu cầu Anki 23.10 trở lên (phát triển và kiểm thử trên Anki 26.08).

## 📊 Bảng điều khiển

Lời chào theo buổi, các nút nhanh, thẻ thống kê, heatmap hoạt động xem được
từng năm một, và đồng hồ Pomodoro vẫn chạy khi bạn đang học. Đếm ngược kỳ thi
nằm ngay dưới lời chào và chuyển màu cam khi còn dưới 14 ngày.

Thanh bên là tuỳ chọn và có hai dạng — đầy đủ hoặc rail icon thu gọn. Khi thanh
bên hiện, danh sách bộ thẻ và phần header chuyển hẳn vào đó, kèm ô tìm bộ thẻ
và icon màu riêng cho từng bộ.

## ✅ Thói quen

Một dải thói quen nằm dưới các thẻ thống kê: một cú nhấp là đánh dấu xong cho
hôm nay, và cú nhấp đó không tải lại trang. Thói quen có thể là dạng có/chưa
hoặc đếm theo mục tiêu (2500 trên 3000 ml, 25 trên 30 phút), và lặp mỗi ngày,
theo thứ đã chọn, hoặc một số lần mỗi tuần — dạng cuối tính theo tuần nên bỏ
thứ Ba cũng không sao miễn là cả tuần đủ số lần.

**Báo cáo** mở ba mức tuần, tháng và năm: lưới bảy ngày kèm tổng theo từng
ngày, một lịch cho mỗi thói quen, và dải cả năm kiểu GitHub, mỗi mức đều có tỉ
lệ hoàn thành, số ngày trọn vẹn và chuỗi dài nhất.

Thói quen được lưu trong collection nên đi kèm bản sao lưu `.colpkg` và đồng bộ
giữa các máy. Xoá một thói quen là lưu trữ nó và giữ nguyên lịch sử; muốn xoá
hẳn thì phải xác nhận riêng.

## 📚 Màn hình bộ thẻ

Nút quay về, icon và mô tả bộ thẻ, ba thẻ đếm, một nút học chính, **dự báo 7
ngày tới** lấy từ ngày đến hạn thật trong lịch, danh sách bộ thẻ con, và hàng
thao tác mờ ở dưới (tuỳ chọn, học tuỳ biến, đổi tên, xuất, mô tả). Hai thanh
gốc của Anki được ẩn ở màn này vì trang đã tự có.

## 🎯 Chế độ học

Bốn cách học một bộ thẻ theo kiểu Quizlet, mở bằng nút **Chế độ học** ở màn
hình bộ thẻ. Chúng chạy ngay trong cửa sổ hiện tại — không có webview thứ hai,
không phải ứng dụng riêng — và mặc định không đụng gì tới lịch ôn tập.

| Chế độ | Nội dung |
| --- | --- |
| **Thẻ lật** | Lật thẻ theo nhịp của bạn, xáo trộn, phát âm thanh |
| **Học** | Từng vòng bảy thẻ, khó dần khi bạn đã nhớ: đúng/sai, rồi trắc nghiệm, rồi tự gõ. Sai một câu là tụt lại một bậc |
| **Kiểm tra** | Số câu cố định, trộn nhiều dạng, chấm điểm ở cuối kèm danh sách câu sai |
| **Ghép cặp** | Ghép từ với nghĩa, tính giờ, lưu kỷ lục riêng cho từng bộ thẻ |

Câu tự gõ chấp nhận lỗi chính tả nhẹ — đảo hai chữ cái, hoặc sai một ký tự ở từ
dài — và nói rõ là "gần đúng" chứ không lặng lẽ cho qua; trường chứa nhiều nghĩa
thì gõ nghĩa nào cũng được. Phiên Học được lưu trong collection nên còn nguyên
sau khi tắt Anki và đồng bộ được giữa các máy.

**Trường nào ở mặt trước, trường nào ở mặt sau** được suy ra từ mẫu thẻ chứ
không phải theo thứ tự khai báo — nên loại thẻ có trường đầu tiên là số thứ tự
vẫn ra đúng từ, và thẻ chiều ngược lại là một câu hỏi khác chứ không lặp lại câu
cũ. Chọn ngay trên màn Chế độ học của bộ thẻ đó, mỗi loại thẻ một thiết lập — tối đa
hai trường mặt trước, ba trường mặt sau — trường đầu tiên ở mỗi mặt là trường được hỏi, những trường còn
lại hiện kèm bên cạnh, và mọi đáp án đều có nút **Chi tiết** mở ra toàn bộ thẻ
đúng như màn ôn tập vẫn vẽ. Độ dài phiên và dạng câu hỏi cũng chỉnh ở đó, trên
chính bộ thẻ, thay vì trong một cửa sổ riêng. Thẻ Cloze
và Image Occlusion để dành cho trình ôn tập của Anki.

## 🎴 Màn ôn thẻ

Thanh trên (quay về, tên bộ thẻ, sửa, thao tác khác) và thanh dưới (số thẻ còn
lại, nút Hiện đáp án hoặc bốn nút chấm điểm) đều nằm trong trang, nên toolbar
và thanh trả lời gốc của Anki có thể lui ra. Mốc thời gian trên nút chấm điểm
lấy từ scheduler nên theo đúng cấu hình bộ thẻ và FSRS.

**Giao diện thẻ** là tuỳ chọn, dựng lại mặt sau từ các trường của note — cách
đọc phía trên từ, nút phát âm thanh, danh sách nghĩa đánh số, hình ảnh, phần ví
dụ và ghi chú thu gọn được — kèm animation lật ngang. Bấm hoặc nhấn Space để
lật; chấm điểm bằng phím mũi tên hoặc vuốt chuột, thẻ sẽ bay đi.

**Chấm tự động** là tuỳ chọn còn lại, và nó thay đổi cách bạn trả lời. Nút Hiện
đáp án vẫn y như cũ, bên dưới có thêm thanh đếm ngược cho biết bạn đang ở vùng
nào — và thời gian bạn mất tới lúc đó sẽ chọn Dễ, Tốt hay Khó thay bạn. Để
thanh cạn thì đáp án tự hiện và thẻ bị chấm Lại. Sang mặt đáp án, bạn chỉ cần
nói mình có thuộc hay không — **←** không, **→** có, **Space** để xác nhận —
thay vì tự chấm mức độ; các phím được ghi ngay dưới thẻ. Bốn nút chấm điểm được
ẩn đi, và chỉ cần bấm vào kết quả là chúng hiện lại, với mức đã chọn được đánh
dấu sẵn — chấm nhầm thì sửa trong một cú bấm. Đồng hồ
dừng mỗi khi Anki không phải cửa sổ đang dùng, nên rời máy một lát không bao
giờ mất thẻ, và thời gian đọc đáp án không bao giờ bị tính. Đặt các mốc thời
gian — chung hoặc theo từng bộ thẻ — trong **Cài đặt → Bộ thẻ**.

Cạnh nút sửa còn có nút **hoàn tác**, trả lại thẻ bạn vừa trả lời; thông báo
xác nhận của Anki cũng được vẽ theo màu của theme.

## ⚙️ Cài đặt trong add-on

Tám trang, bố cục theo kiểu macOS System Settings:

| Trang | Nội dung |
| --- | --- |
| 📋 Chung | Tên, lời chào, ngôn ngữ, chế độ thanh bên, các khối trên dashboard, độ dài Pomodoro |
| 🎨 Giao diện | Chủ đề, chế độ sáng/tối, chọn màn hình được áp theme, ẩn thanh gốc của Anki |
| 🗂️ Bộ thẻ | Giao diện thẻ và chấm tự động theo từng bộ, mốc thời gian trả lời, và đổi tên / tuỳ chọn / xuất / xoá |
| 🧠 FSRS | Bật FSRS, mức ghi nhớ mong muốn, tối ưu và đánh giá tham số |
| 🎯 Chế độ học | Có hiện chế độ học hay không, và có cho phép chấm điểm thẻ hay không |
| 📅 Sự kiện | Danh sách đếm ngược kỳ thi |
| ✅ Thói quen | Danh sách thói quen: thêm, sửa, đổi thứ tự, lưu trữ |
| ℹ️ Giới thiệu | Phiên bản, bản webview đang chạy và các tuỳ chọn đặt lại |

Các khoá cấu hình được mô tả trong [config.md](config.md). Nên chỉnh trong hộp
thoại thay vì sửa JSON trực tiếp.

### 🧠 FSRS

Anki đã tích hợp sẵn scheduler FSRS; add-on gom mọi thứ về một chỗ — bật/tắt
toàn cục, mức ghi nhớ mong muốn theo từng bộ cấu hình, tối ưu và đánh giá tham
số, cùng số ngày kể từ lần tối ưu gần nhất.

### 🎨 Chủ đề

Sáu chủ đề (Terracotta, Glass — Apple HIG, Matcha, Aurora, Sunset, Sakura),
mỗi chủ đề có bảng màu sáng và tối — Aurora và Sunset tô màu nhấn bằng chuyển
màu — kèm công tắc **Theo hệ thống / Sáng / Tối**
đổi luôn giao diện của Anki. Khi đổi, trang đang mở sẽ chuyển màu mượt thay vì
vẽ lại. Có thể đồng bộ chủ đề cho các màn hình khác của Anki (Thêm thẻ, Duyệt,
Thống kê, hộp thoại) qua biến CSS và bảng màu Qt.

### 🌐 Ngôn ngữ

Tiếng Việt, English, Português (Brasil) và 日本語, mặc định theo ngôn ngữ của
Anki. Mọi chuỗi nằm
trong `i18n/<mã>.json` — chép `en.json`, dịch phần `strings`, khởi động lại là
ngôn ngữ mới xuất hiện trong Cài đặt. Mỗi file cũng tự mang tên tháng, thứ, dấu
phân cách hàng nghìn và thứ tự ngày tháng riêng nên ngày hiển thị tự nhiên. Key
nào thiếu sẽ tự lùi về tiếng Anh nên dịch dở dang vẫn dùng được. Chạy `python3
tools/check_locales.py` để soát chỗ thiếu.

Các màn hình gốc của Anki — thanh công cụ, Thêm thẻ, Duyệt, tuỳ chọn bộ thẻ,
kể cả nhãn 4 nút chấm điểm — đi theo ngôn ngữ của Anki chứ không theo cài đặt
này. Nên sau khi bạn chọn ngôn ngữ, add-on sẽ hỏi có đổi luôn ngôn ngữ Anki và
khởi động lại không. Nếu từ chối thì ngôn ngữ cũ được giữ nguyên, tránh để hai
bên lệch nhau.

## 📥 Cài đặt

**Từ AnkiWeb** — trong Anki, mở **Tools → Add-ons → Get Add-ons…** rồi dán mã
[`1243176816`](https://ankiweb.net/shared/info/1243176816). Các bản cập nhật sau
đó sẽ về tự động.

**Từ file** — tải file `.ankiaddon` ở
[release mới nhất](https://github.com/kpdo2910/awesome-dashboard/releases/latest),
rồi **Tools → Add-ons → Install from file…** và chọn file đó.

Cách nào cũng cần khởi động lại Anki, sau đó mở **Tools → Cài đặt Awesome
Dashboard…** (hoặc nút ⚙ trên bảng điều khiển).

## 📄 Giấy phép

MIT — xem [LICENSE](LICENSE).
