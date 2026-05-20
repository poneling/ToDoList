# Günlük To-Do List

Premium minimalist çizgide geliştirilmiş Windows masaüstü yapılacaklar listesi uygulaması.

## Özellikler

- CustomTkinter ile koyu, modern ve minimalist arayüz
- Sol menü ile çoklu liste/kategori desteği
- Her liste için ayrı görev havuzu
- Görev ekleme, tamamlama ve silme
- Görevleri sürükle-bırak ile yeniden sıralama
- Tamamlanan görevleri soluk ve üstü çizili gösterme
- Görevleri ve listeleri hiyerarşik JSON dosyasında kalıcı saklama
- Windows başlangıcında otomatik açılmak için Startup klasörüne kısayol oluşturma

## Kurulum

```powershell
python -m pip install -r requirements.txt
python main.py
```

Görev verileri şu dosyada tutulur:

```text
%APPDATA%\GunlukTodoList\todo_data.json
```

Eski `tasks.json` verisi varsa uygulama ilk açılışta otomatik olarak yeni liste yapısına taşır.

## EXE Oluşturma

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name GunlukTodoList --collect-data customtkinter main.py
```

Oluşan dosya:

```text
dist\GunlukTodoList.exe
```

## Windows Başlangıcı

Uygulama açıldığında şu başlangıç kısayolunu otomatik oluşturur veya günceller:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Gunluk To-Do List.lnk
```
