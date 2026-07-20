@echo off
REM Compila Spotlight-Key con PyInstaller: un ejecutable para el tray
REM (el que arranca solo con Windows) y otro para la GUI completa.
REM Correr desde la raiz del proyecto, con el venv activado.
REM Requiere: pip install pyinstaller  (una sola vez, no va en requirements.txt
REM porque es una herramienta de build, no algo que la app necesite en runtime)

echo Compilando SpotlightKey-Tray...
pyinstaller --noconsole --name SpotlightKey-Tray ^
    --icon=spotlight-key.ico ^
    --collect-all PySide6 ^
    --hidden-import pystray._win32 ^
    --add-data "sources/SVG;sources/SVG" ^
    tray\__main__.py

echo Compilando SpotlightKey (GUI)...
pyinstaller --noconsole --name SpotlightKey ^
    --icon=spotlight-key.ico ^
    --collect-all PySide6 ^
    --add-data "sources/SVG;sources/SVG" ^
    gui\__main__.py

echo.
echo Listo. Los ejecutables quedaron en:
echo   dist\SpotlightKey-Tray\SpotlightKey-Tray.exe
echo   dist\SpotlightKey\SpotlightKey.exe
pause