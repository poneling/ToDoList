# Günlük To-Do List

Minimalist ve modern görünümlü Windows masaüstü yapılacaklar listesi uygulaması.

## Özellikler

- CustomTkinter ile modern dark/light mode arayüz
- Görev ekleme, tamamlama ve silme
- Tamamlanan görevleri soluk ve üstü çizili gösterme
- Görevleri yerel JSON dosyasında kalıcı saklama
- Windows başlangıcında otomatik açılmak için Startup klasörüne kısayol oluşturma

## Kurulum

```powershell
python -m pip install -r requirements.txt
python main.py
```

Görev verileri şu klasörde tutulur:

```text
%APPDATA%\GunlukTodoList\tasks.json
```

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
