# FloatLand

[English](README.md) · **Русский**

> **Дисклеймер:** проект сделан с помощью ИИ.

Плавающие окна для [Hyprland](https://hyprland.org/) со встроенными удобствами.
Это несерьёзный проект, я сделал его для себя, но он может понравиться и вам.

**Цель:** Hyprland **0.56.2** (для сборки нужны заголовки именно установленной версии).
**Текущая версия:** 0.6.5e — экспериментальная. Последняя версия без суффикса `e` — 0.6.1.1.

## Возможности

- **Переключение floating / tiling** с запоминанием геометрии окон
- **Запоминание размеров** — последний обычный floating-размер каждого приложения
- **Заголовки окон** — нативные, настраиваемые кнопки (закрыть / свернуть / развернуть): сторона, порядок, цвета, анимации
- **Snap** — перетащите заголовок к краю экрана или в верхнюю палитру
- **Alt+Tab** с тремя стилями: `icons`, `preview` (миниатюры) и `legacy`; поддержка мыши
- **Overview** — окна текущего рабочего стола, сгруппированные по приложению (`Super+G`)
- **Настройка на Lua** с автоматическим применением после сохранения
- **Необязательно, экспериментально:** прототип заголовка для Qt ([integrations/qt](integrations/qt/README.md))

## Требования

- Python 3.9+
- CMake 3.22+, компилятор C++23, pkg-config
- Заголовки Hyprland 0.56.2
- pixman, libdrm, libinput, libudev, wayland-server, xkbcommon, pangocairo, librsvg
- Интерпретатор Lua (`lua`, `lua5.4`, `lua5.3` или `luajit`) либо Python-пакет `lupa`

## Установка и запуск

```sh
git clone https://github.com/Verraier/Floatland.git
cd Floatland
python3 run.py
```

Сборка, загрузка плагина и запуск демона происходят автоматически. Терминал оставьте открытым.
Журнал: `logs/session.log`. Остановка: `Ctrl+C` или `python3 run.py stop`.

Конфиг Hyprland автоматически **не** меняется. Пример ручного подключения:
[examples/hyprland.lua](examples/hyprland.lua).

## Настройка

При первом запуске конфиг создаётся в `~/.config/floatland/` (учитывается `$XDG_CONFIG_HOME`).
Редактируйте эти файлы, а не шаблоны в папке с исходниками.

```text
~/.config/floatland/
├── init.lua
└── config/
    ├── windows.lua
    ├── titlebars.lua
    ├── snapping.lua
    ├── overview.lua
    ├── switching.lua
    ├── bindings.lua
    └── theme.lua
```

```sh
python3 run.py config init        # создать конфиг без запуска Hyprland
python3 run.py config path        # путь к init.lua
python3 run.py config show        # проверить и показать итоговые значения
python3 run.py config reference   # справочник всех параметров
python3 run.py config format      # привести старые сгенерированные Lua-файлы к шаблонам с комментариями
python3 run.py reload             # применить вручную (автоприменение при сохранении тоже работает)
```

Пример, `config/switching.lua`:

```lua
style = "icons",    -- "icons", "preview" или "legacy"
mouse = true,       -- наведение выбирает; отпустить Alt или кликнуть — активировать
```

Полный справочник: [docs/configuration.md](docs/configuration.md).

## Управление

| Клавиши / действие | Что делает |
|---|---|
| `Alt+Tab` | Переключение окон (отпустить Alt — выбрать, `Esc` — отмена; `Tab` листает страницы) |
| `Super+G` | Overview текущего рабочего стола (клик / `Enter` — выбрать, стрелки / колесо — перемещение, `Esc` или `Super+G` — закрыть) |
| Перетащить заголовок к краю / в палитру | Snap |
| `python3 run.py toggle` | floating ⇄ tiling |
| `python3 run.py snap left`, `maximize`, `restore`, `center`, `minimize`, `pin` | Команды окон |

## Прототип заголовка для Qt (экспериментально)

Необязательный модуль рисует заголовок внутри окна приложения на Qt 6.
Это первый прототип: нужен Qt 6.8+ с private-заголовками, он **не собирался и не проверялся на Linux**,
snap-жесты пока не подключены. На обычную работу Floatland он не влияет.

```sh
python3 run.py qt -- your-qt6-application
```

Подробности, ограничения и откат: [integrations/qt/README.md](integrations/qt/README.md).

## Разработка

```sh
python3 tools/check.py   # тесты Python/Lua и независимые тесты C++
```

Структура: `src/floatland/` (Python), `native/` (C++ плагин), `integrations/` (необязательное), `tests/`, `docs/`, `examples/`.
См. [docs/architecture.md](docs/architecture.md) (на английском).

## Статус

Логика проверена на macOS; полный плагин нужно ещё тестировать на реальном Hyprland.
Возможны шероховатости. Известно: `Alt+Shift+Tab` (переключение назад) пока **не работает**;
падение Hyprland после overview → другой рабочий стол → Steam пока не объяснено
([docs/bugs](docs/bugs/2026-10-19-steam-after-overview.md)). См. [CHANGELOG.md](CHANGELOG.md).

## Благодарности

Большое спасибо, без этих проектов ничего бы не получилось:

- **[hyprstack-shell](https://github.com/hase9awa/hyprstack-shell)** (hase9awa и участники, GPL-3.0) —
  модель floating/tiling, память геометрии и snap-зоны изучены по нему; `native/check_sdk.py`
  адаптирует его проверку заголовков/ABI.
- **[hyprbars](https://github.com/hyprwm/hyprland-plugins/tree/428bfcd1c9ee34965400bb359349f518140c9920/hyprbars)**
  (Hypr Development, BSD-3-Clause) — подход к декорации окна, render-pass и вводу в
  `native/titlebar.cpp` производен от него.
- **[Hyprland](https://github.com/hyprwm/Hyprland)** (vaxerski и участники, BSD-3-Clause) — композитор
  и API плагинов (сверено с v0.56.2).
- **[Hyprtasking](https://github.com/raybbian/hyprtasking)** (Raymond Bian и участники, BSD-3-Clause) —
  API overview и поведение ввода сверялись с ним; необязательная старая интеграция в
  `src/floatland/overview.py` ставит его через hyprpm.
- **[Qt](https://www.qt.io/)** — необязательный прототип использует Qt 6 пользователя
  (приватные интерфейсы декораций qtwayland); исходники Qt не включены.
- Библиотеки: Pango, Cairo, librsvg, pixman, libdrm, libinput, xkbcommon, wayland, а также Lua /
  [lupa](https://github.com/scoder/lupa) для настройки.

Подробности и уведомления о сторонних компонентах: [NOTICE.md](NOTICE.md), [native/NOTICE.md](native/NOTICE.md).

## Лицензия

GPL-3.0-or-later — см. [LICENSE](LICENSE). Нативный код, производный от Hyprbars, сохраняет своё
уведомление BSD-3-Clause в [native/LICENSE.hyprbars](native/LICENSE.hyprbars).
