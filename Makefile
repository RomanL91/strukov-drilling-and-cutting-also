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

# Сборка .app (запускать только на macOS).
# Права доступа и метаданные берутся из [tool.flet] в pyproject.toml.
build-macos:
	poetry run flet build macos --yes

clean:
	poetry run flet clean
