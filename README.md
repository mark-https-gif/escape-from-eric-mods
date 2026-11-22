# Erik Mod Shop — каталог модов Escape From Eric

Каталог модов для игры (Efe Runtime). Приём модов — **через GitHub**, без Telegram-бота.

## Как предложить мод

1. Соберите и подпишите пакет в SDK:
   ```
   efepack check  C:\Mods\MyMod
   efepack sign   C:\Mods\MyMod --key C:\Keys\efe-mods-private.key
   ```
   Получится `<id>-<версия>.efemod` (только контент, **без DLL**).

2. В этом репозитории создайте папку `mods/<id>/` и положите:
   - `<id>-<версия>.efemod`
   - `mod.json` (описание, версия, sha256)
   - `preview.png` (обложка)

3. Откройте **Pull Request**. CI проверит:
   - `sha256` в `mod.json` совпадает с файлом;
   - пакет не больше 1 МБ;
   - внутри нет `.exe/.dll/.bat`, `protocol` только `lua`;
   - подпись Ed25519 верна и ключ — доверенный TITEL.

4. После мержа `mods.json` обновится автоматически, и мод появится в игре в **ERIK MODSHOP**.

## Локальная проверка

```bash
pip install pynacl
python scripts/check_mods.py
```

Пересобрать каталог вручную:

```bash
python scripts/check_mods.py --write
```

## Структура

```
mods.json                     индекс для игры
mods/<id>/mod.json            карточка мода
mods/<id>/preview.png         обложка
mods/<id>/<id>-<ver>.efemod   подписанный пакет
scripts/check_mods.py         проверка каталога
```
