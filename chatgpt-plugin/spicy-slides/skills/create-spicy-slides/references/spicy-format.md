# Формат файла SPICY SLIDES

Контракт проверен на HTML-редакторе Spicy от 8 октября 2026 года. Название SPICY SLIDES не меняет расширение `.spicy`. Поддерживаемая этой заготовкой версия документа — `1.0.0`, MIME `application/vnd.spicy.presentation+zip`, компоновка пакета `split-slides-v1`. Не путай её с экспериментальной схемой `2.0.0`.

## Создание в GPT-чате

1. Загрузи `assets/starter.json` относительно каталога навыка. Это полный документ, а не manifest. Для новой презентации обнови `documentId`, даты, название, текст и композицию. Сначала просмотри встроенные примеры карточек.
2. Создавай слайды по образцу первого: новая запись `slides`, своя `scene` и корневой `frame`. Для каждого экземпляра нужны уникальные ID, включая детей и действия. Внеси слайд в `slideOrder` и в `settings.presentationOutline`: запись слайда `{id, type:"slide", slideId}`, блок `{id, type:"block", name, color, children}`, папка `{id, type:"group", name, children}`. `rootIds` содержит блоки; родитель перечисляет детей в `children`. Порядок обхода дерева должен совпадать с `slideOrder`. В дереве презентации поле `parentId` не нужно.
3. Оставь обязательные поля пустыми коллекциями, когда они не используются; не удаляй их. Сверяй структуру с шаблоном. Не переноси ID демонстрационных объектов между слайдами без переименования.
4. Запиши полный документ UTF-8 JSON и локальные ресурсы. Выполни:

```sh
python3 scripts/package_spicy.py document.json presentation.spicy --resource-root resources
```

Пути в этой команде относятся к каталогу навыка либо должны быть абсолютными. `--resource-root` нужен только при ресурсах. Путь ресурса внутри JSON, например `assets/<sha256>.png`, отсчитывается от этого каталога. Существующий выходной файл не перезаписывается. Выдай полученный `.spicy` как файл для скачивания средствами GPT-чата.

Скрипт выполняет структурную проверку и создаёт стандартный ZIP с отдельными JSON слайдов и SHA-256 по фактическим байтам. Он не заменяет полный validator приложения и визуальную проверку.

## Узлы и координаты

Канонические поля узла: `id`, `type`, `name`, `parentId`, `children`, `geometry`, `style`, `layout`, `content`, `interactionIds`, `animationIds`, `visible`, `locked`, `accessibility`, `source`, `pluginData`. Геометрия: `x`, `y`, `width`, `height`, `rotation`. Начало координат — начало непосредственного родителя. Базовый слайд шаблона — 1600 × 900 px. CSS-размеры текста — в этих единицах, а не в `vw`, `vh` или долях ширины бокса. Масштабирование всей сцены выполняет редактор.

Пример текста — `type: "html"` с такими `content`:

```json
{
  "role": "text",
  "textEditable": true,
  "assetIds": [],
  "markup": "<div data-eid=\"caption\" style=\"width:100%;height:100%;box-sizing:border-box;font:32px/1.2 Arial,sans-serif;color:#17212b\">Обычный <strong>жирный</strong>, <em>курсивный</em> и <strong><em><u>всё вместе</u></em></strong> текст</div>"
}
```

Корневой фрагмент занимает геометрию узла; не записывай в нём второй набор абсолютных координат слайда. Для бокса используй отдельный HTML `div` с фоном, границей и скруглением, для простой фигуры — SVG. Прямоугольник и его подпись могут быть соседями в `group`; тогда координаты обоих локальные. Фон слайда — `rootFrame.style.background` или штатный формат фонового ресурса, не картинка поверх всей сцены с включённым текстом.

## Изображения и файлы

Для нового изображения посчитай SHA-256 исходных байтов. В `document.assets[id]` сохрани `{id, path, mimeType, size, sha256, name}`; ID по текущей практике — сам хеш, путь `assets/<hash>.<ext>`. У узла изображения `content.assetIds` содержит этот ID, а `content.markup`:

```html
<img data-eid="photo" src="spicy-asset://ASSET_ID" alt="Описание изображения" style="width:100%;height:100%;box-sizing:border-box;object-fit:contain;display:block">
```

Замени `ASSET_ID` фактическим ID. Не используй машинные `file://`, временные `blob:`, внешние обязательные CDN или выдуманные имена картинок. Для `embed` запиши metadata `{id, entryPoint, files, sandboxProfile:"spicy-html-v1", bridgeVersion:1, permissions:[]}`, узел с `content.bundleId`, а файлы размести как `embeds/<bundleId>/<relativePath>` в каталоге ресурсов. Виджет занимает только свой бокс; обычные надписи и подписи вокруг него остаются обычными узлами.

## При наличии исходников приложения

Предпочитай реальные `model/document.js`, `features/spicy-object-factory.js`, `features/spicy-project-controller.js`, `format/package-writer.js` и `format/package-reader.js` из явно выбранного каталога приложения. Проверяй текущие сигнатуры, а не абсолютный путь чужого компьютера. Стандартный экспорт HTML — `scripts/export-presentation-html.cjs input.spicy output.html`. Плагин не включает редактор и не выдаёт наличие репозитория на GitHub за доступ к нему в среде GPT.

