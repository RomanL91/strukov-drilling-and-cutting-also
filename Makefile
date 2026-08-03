.PHONY: install run dev build-windows pack-windows build-macos clean

install:
	poetry install

# Обычный запуск десктопного окна
run:
	poetry run python main.py

# Запуск с горячей перезагрузкой при правке кода
dev:
	poetry run flet run --hot main.py

# Сборка .exe нативным бандлом Flutter (запускать на Windows).
# Требует Visual Studio с workload «Desktop development with C++»
# (подойдёт и Build Tools) — без него flutter не находит тулчейн.
build-windows:
	poetry run flet build windows

# Сборка .exe одним файлом через PyInstaller (запускать на Windows).
# Visual Studio не нужен: flet-клиент уже собран и вкладывается в exe.
# Метаданные [tool.flet] сюда не применяются, поэтому передаём их флагами.
pack-windows:
	poetry run flet pack main.py --name StrukovDrilling \
		--product-name "Струков — сверление и резка" \
		--file-description "Передача производственных заданий на линию сверления и отреза" \
		--company-name "Струков" \
		--copyright "© Струков" \
		--product-version $(shell poetry version -s) \
		--file-version $(shell poetry version -s).0 \
		--yes

# Сборка .app (запускать только на macOS).
# Права доступа и метаданные берутся из [tool.flet] в pyproject.toml.
build-macos:
	poetry run flet build macos --yes

clean:
	poetry run flet clean
