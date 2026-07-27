.PHONY: install run dev build-windows build-macos clean

install:
	poetry install

# Обычный запуск десктопного окна
run:
	poetry run python main.py

# Запуск с горячей перезагрузкой при правке кода
dev:
	poetry run flet run --hot main.py

# Сборка .exe (запускать на Windows)
build-windows:
	poetry run flet build windows

# Сборка .app (запускать только на macOS)
build-macos:
	poetry run flet build macos \
		--macos-entitlements com.apple.security.network.client=true

clean:
	poetry run flet clean
