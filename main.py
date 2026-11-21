import json
import os
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import flet as ft


def get_storage_dir() -> Path:
    flet_data = os.getenv("FLET_APP_STORAGE_DATA")
    if flet_data:
        return Path(flet_data)
    return Path.home() / ".mi_app_de_novelas"


def get_downloads_dir() -> Path:
    android_downloads = Path("/storage/emulated/0/Download")
    if android_downloads.exists():
        return android_downloads
    flet_temp = os.getenv("FLET_APP_STORAGE_TEMP")
    if flet_temp:
        return Path(flet_temp)
    return Path.home() / "Downloads"


APP_DIR = get_storage_dir()
DATA_FILE = APP_DIR / "proyectos.json"

MODES = {"narration", "dialogue", "thought", "title"}
MARGINS = {
    "narrow": ("Estrecho", 28),
    "normal": ("Normal", 48),
    "wide": ("Amplio", 72),
}


def empty_page():
    return [{"text": "", "mode": "narration"}]


def load_store():
    default = {"projects": [], "default_font_size": 10}

    try:
        if not DATA_FILE.exists():
            return default

        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default

        if not isinstance(data.get("projects"), list):
            data["projects"] = []

        size = data.get("default_font_size", 10)
        data["default_font_size"] = min(18, max(6, int(size)))
        return data
    except (OSError, ValueError, TypeError):
        return default


def save_store(store):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temporary_file = DATA_FILE.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(DATA_FILE)
        return True
    except OSError:
        return False


def clean_title(title):
    return title.strip() or "Borrador sin título"


def filename_slug(title):
    normalized = unicodedata.normalize("NFKD", clean_title(title))
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    return slug or "borrador"


def page_as_text(paragraphs):
    return "\n\n".join(
        paragraph.get("text", "")
        for paragraph in paragraphs
    )


def create_project(font_size):
    return {
        "id": str(uuid.uuid4()),
        "title": "Nuevo proyecto",
        "pages": [empty_page()],
        "current_page": 0,
        "margins": "normal",
        "font_size": font_size,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def project_character_count(project):
    return sum(
        len(paragraph.get("text", ""))
        for sheet in project.get("pages", [])
        for paragraph in sheet
    )


def main(page: ft.Page):
    store = load_store()
    projects = store["projects"]

    active_project = None
    current_page = 0
    active_mode = "narration"

    page.title = "Mi App de Novelas"
    page.bgcolor = "#f4f0e6"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    def persist_project():
        if active_project:
            active_project["title"] = clean_title(active_project.get("title", ""))
            active_project["updated_at"] = datetime.now().isoformat(
                timespec="seconds"
            )
        return save_store(store)

    def open_project(project_id):
        nonlocal active_project, current_page, active_mode

        active_project = next(
            (project for project in projects if project["id"] == project_id),
            None,
        )
        if not active_project:
            show_projects()
            return

        active_project.setdefault("pages", [empty_page()])
        if not active_project["pages"]:
            active_project["pages"] = [empty_page()]

        for sheet in active_project["pages"]:
            for paragraph in sheet:
                if paragraph.get("mode") not in MODES:
                    paragraph["mode"] = "narration"
                paragraph.setdefault("text", "")
            if not sheet:
                sheet.extend(empty_page())

        current_page = min(
            max(0, active_project.get("current_page", 0)),
            len(active_project["pages"]) - 1,
        )
        show_editor()

    def create_new_project(_=None):
        nonlocal active_project, current_page, active_mode

        active_project = create_project(store["default_font_size"])
        projects.insert(0, active_project)
        current_page = 0
        active_mode = "narration"
        persist_project()
        show_editor()

    def show_home(_=None):
        page.clean()

        menu = ft.Column(
            controls=[
                ft.Text(
                    "Escribe tu historia",
                    size=42,
                    weight=ft.FontWeight.BOLD,
                    color="#263a33",
                ),
                ft.Text(
                    "Tu espacio creativo personal",
                    size=16,
                    color="#68756f",
                ),
                ft.Container(height=12),
                ft.ElevatedButton(
                    "1. Empezar a crear",
                    width=300,
                    on_click=create_new_project,
                ),
                ft.ElevatedButton(
                    "2. Ajustes",
                    width=300,
                    on_click=show_settings,
                ),
                ft.ElevatedButton(
                    "3. Proyectos guardados",
                    width=300,
                    on_click=show_projects,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
        )

        page.add(
            ft.Container(
                content=menu,
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )

    def show_projects(_=None):
        page.clean()

        rows = []
        for project in sorted(
            projects,
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        ):
            project_id = project["id"]
            title = clean_title(project.get("title", ""))
            sheet_count = len(project.get("pages", []))
            characters = project_character_count(project)

            rows.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.BOOK),
                    title=ft.Text(title),
                    subtitle=ft.Text(
                        f"{sheet_count} hojas · {characters} caracteres"
                    ),
                    on_click=lambda e, item_id=project_id: open_project(item_id),
                )
            )

        if not rows:
            rows.append(
                ft.Text("Todavía no hay borradores guardados.")
            )

        page.add(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.TextButton("← Menú principal", on_click=show_home),
                            ft.Text(
                                "Proyectos guardados",
                                size=28,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Divider(),
                    *rows,
                    ft.ElevatedButton(
                        "Nuevo borrador",
                        icon=ft.Icons.ADD,
                        on_click=create_new_project,
                    ),
                ],
                spacing=12,
                expand=True,
            )
        )

    def show_settings(_=None):
        page.clean()

        current_size = (
            active_project.get("font_size", 10)
            if active_project
            else store.get("default_font_size", 10)
        )
        size_label = ft.Text(f"{current_size} pt")
        scope_label = (
            "Tamaño base del proyecto"
            if active_project
            else "Tamaño base para proyectos nuevos"
        )

        def change_default_size(event):
            value = int(round(event.control.value))
            size_label.value = f"{value} pt"

            if active_project:
                active_project["font_size"] = value
                persist_project()
            else:
                store["default_font_size"] = value
                save_store(store)

            page.update()

        back_action = show_editor if active_project else show_home

        page.add(
            ft.Column(
                controls=[
                    ft.TextButton("← Volver", on_click=back_action),
                    ft.Text(
                        "Ajustes",
                        size=30,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Divider(),
                    ft.Text(scope_label),
                    ft.Row(
                        controls=[
                            ft.Slider(
                                min=6,
                                max=18,
                                divisions=12,
                                value=current_size,
                                on_change=change_default_size,
                                expand=True,
                            ),
                            size_label,
                        ],
                    ),
                    ft.Text(
                        "Los títulos se muestran en negrita y a 1,4 veces "
                        "el tamaño base."
                    ),
                ],
                width=600,
                spacing=16,
            )
        )

    def show_guide(_=None):
        def close_dialog(_):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Guía de escritura"),
            content=ft.Column(
                controls=[
                    ft.Text("Diálogo: comienza con la raya (—)."),
                    ft.Text("Pensamiento: se muestra en cursiva."),
                    ft.Text("Narración: utiliza el tamaño base del proyecto."),
                    ft.Text("Título: se muestra en negrita, a 1,4× el tamaño base."),
                    ft.Text("Los borradores se guardan en este dispositivo."),
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Entendido", on_click=close_dialog),
            ],
        )
        page.dialog = dialog
        dialog.open = True
        page.update()
          def show_editor():
        nonlocal active_mode

        if not active_project:
            show_projects()
            return

        sheets = active_project["pages"]
        if current_page >= len(sheets):
            sheets.append(empty_page())

        paragraphs = sheets[current_page]
        if not paragraphs:
            paragraphs.extend(empty_page())

        first_mode = paragraphs[-1].get("mode", "narration")
        active_mode = first_mode if first_mode in MODES else "narration"

        page.clean()

        status_text = ft.Text(
            "Guardado en este dispositivo",
            size=11,
            color="#68756f",
        )
        download_status = ft.Text(
            "",
            size=11,
            color="#3e6256",
            selectable=True,
        )
        paragraph_fields = []

        def save_status():
            status_text.value = (
                "Guardado en este dispositivo"
                if persist_project()
                else "No se pudo guardar el borrador"
            )
            status_text.update()

        def update_title(event):
            active_project["title"] = event.control.value
            save_status()

        def update_paragraph(index, event):
            paragraphs[index]["text"] = event.control.value or ""
            save_status()

        def add_mode_paragraph(mode):
            nonlocal active_mode

            initial_empty = (
                len(paragraphs) == 1
                and not paragraphs[0].get("text", "").strip()
            )

            if initial_empty:
                paragraphs[0]["mode"] = mode
                paragraphs[0]["text"] = "— " if mode == "dialogue" else ""
            else:
                paragraphs.append(
                    {
                        "mode": mode,
                        "text": "— " if mode == "dialogue" else "",
                    }
                )

            active_mode = mode
            save_status()
            show_editor()

        def add_dialogue_with_thought(_=None):
            nonlocal active_mode

            initial_empty = (
                len(paragraphs) == 1
                and not paragraphs[0].get("text", "").strip()
            )

            dialogue = {"mode": "dialogue", "text": "— "}
            thought = {"mode": "thought", "text": ""}

            if initial_empty:
                paragraphs[0].update(dialogue)
            else:
                paragraphs.append(dialogue)

            paragraphs.append(thought)
            active_mode = "thought"
            save_status()
            show_editor()

        def change_margins(value):
            active_project["margins"] = value
            save_status()
            show_editor()

        def change_font_size(event):
            value = int(round(event.control.value))
            active_project["font_size"] = value
            font_label.value = f"{value} pt"
            font_label.update()

            for index, text_field in enumerate(paragraph_fields):
                mode = paragraphs[index].get("mode", "narration")
                text_field.text_style = text_style(mode, value)
                text_field.update()

            save_status()

        def text_style(mode, base_size):
            size = base_size * 1.4 if mode == "title" else base_size
            return ft.TextStyle(
                size=size,
                italic=(mode == "thought"),
                weight=(
                    ft.FontWeight.BOLD
                    if mode == "title"
                    else ft.FontWeight.NORMAL
                ),
                color="#293630",
            )

        title_input = ft.TextField(
            label="Título del proyecto",
            value=active_project.get("title", ""),
            on_change=update_title,
            border_color="#d8d2c6",
            focused_border_color="#3e6256",
        )

        mode_buttons = []
        mode_names = [
            ("narration", "Narración"),
            ("thought", "Pensamiento"),
            ("title", "Título"),
        ]

        for mode, label in mode_names:
            is_active = active_mode == mode
            mode_buttons.append(
                ft.ElevatedButton(
                    label,
                    on_click=lambda e, selected_mode=mode: add_mode_paragraph(
                        selected_mode
                    ),
                    style=ft.ButtonStyle(
                        bgcolor="#3e6256" if is_active else "#eee9df",
                        color="#ffffff" if is_active else "#293630",
                    ),
                )
            )

        dialogue_menu = ft.PopupMenuButton(
            icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
            tooltip="Opciones de diálogo",
            items=[
                ft.PopupMenuItem(
                    text="Solo diálogo",
                    on_click=lambda e: add_mode_paragraph("dialogue"),
                ),
                ft.PopupMenuItem(
                    text="Diálogo con pensamiento",
                    on_click=add_dialogue_with_thought,
                ),
            ],
        )

        toolbar = ft.Row(
            controls=[
                dialogue_menu,
                *mode_buttons,
                ft.TextButton("Guía", on_click=show_guide),
            ],
            wrap=True,
            spacing=8,
        )

        margin_buttons = []
        current_margin = active_project.get("margins", "normal")

        for margin_key, (label, _) in MARGINS.items():
            margin_buttons.append(
                ft.ElevatedButton(
                    label,
                    on_click=lambda e, selected=margin_key: change_margins(
                        selected
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=(
                            "#3e6256"
                            if current_margin == margin_key
                            else "#eee9df"
                        ),
                        color=(
                            "#ffffff"
                            if current_margin == margin_key
                            else "#293630"
                        ),
                    ),
                )
            )

        margin_controls = ft.Row(
            controls=[
                ft.Text("Márgenes:"),
                *margin_buttons,
            ],
            wrap=True,
            spacing=6,
        )

        base_size = active_project.get("font_size", 10)
        font_label = ft.Text(f"{base_size} pt")
        font_control = ft.Row(
            controls=[
                ft.Text("Tamaño de letra:"),
                ft.Slider(
                    min=6,
                    max=18,
                    divisions=12,
                    value=base_size,
                    on_change=change_font_size,
                    expand=True,
                ),
                font_label,
            ]
        )

        for index, paragraph in enumerate(paragraphs):
            mode = paragraph.get("mode", "narration")
            field = ft.TextField(
                value=paragraph.get("text", ""),
                multiline=True,
                min_lines=1,
                max_lines=6,
                border=ft.InputBorder.NONE,
                content_padding=ft.padding.symmetric(
                    vertical=5,
                    horizontal=0,
                ),
                text_style=text_style(mode, base_size),
                on_change=lambda event, paragraph_index=index: update_paragraph(
                    paragraph_index,
                    event,
                ),
            )
            paragraph_fields.append(field)

        margin_padding = MARGINS.get(current_margin, MARGINS["normal"])[1]
        available_width = page.width or 900
        paper_width = min(560, max(280, int(available_width) - 48))
        paper_height = int(paper_width * 1.414)

        paper_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "MI APP DE NOVELAS",
                            size=10,
                            color="#77766f",
                        ),
                        ft.Text(
                            f"{current_page + 1:02d}",
                            size=10,
                            color="#77766f",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(color="#e5e0d8"),
                ft.Column(
                    controls=paragraph_fields,
                    spacing=4,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            spacing=8,
            expand=True,
        )

        paper = ft.Container(
            content=paper_content,
            width=paper_width,
            height=paper_height,
            padding=ft.padding.symmetric(
                horizontal=margin_padding,
                vertical=36,
            ),
            bgcolor="#ffffff",
            border=ft.border.all(1, "#dedbd5"),
            shadow=ft.BoxShadow(
                blur_radius=24,
                spread_radius=1,
                color="#29000000",
                offset=ft.Offset(0, 10),
            ),
        )

        def export_zip(_=None):
            try:
                title = clean_title(active_project.get("title", ""))
                slug = filename_slug(title)
                downloads = get_downloads_dir()
                downloads.mkdir(parents=True, exist_ok=True)
                zip_path = downloads / f"{slug}.zip"
                pages = active_project.get("pages", [])
                complete_text = [
                    title,
                    "",
                ]
                for index, sheet in enumerate(pages, start=1):
                    complete_text.extend(
                        [
                            f"========== HOJA {index:02d} ==========",
                            "",
                            page_as_text(sheet),
                            "",
                        ]
                    )
                character_count = project_character_count(active_project)
                info_text = "\n".join(
                    [
                        f"Proyecto: {title}",
                        f"Hojas: {len(pages)}",
                        f"Caracteres: {character_count}",
                        f"Exportado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                        "Formato: texto plano UTF-8",
                    ]
                )
                with zipfile.ZipFile(
                    zip_path,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as archive:
                    archive.writestr(
                        f"{slug}/Borrador completo.txt",
                        "\n".join(complete_text),
                    )
                    archive.writestr(
                        f"{slug}/Informacion del proyecto.txt",
                        info_text,
                    )
                    for index, sheet in enumerate(pages, start=1):
                        archive.writestr(
                            f"{slug}/Hojas/Hoja-{index:02d}.txt",
                            page_as_text(sheet),
                        )
                download_status.value = f"ZIP guardado en: {zip_path}"
            except OSError:
                try:
                    fallback_dir = APP_DIR / "exports"
                    fallback_dir.mkdir(parents=True, exist_ok=True)
                    zip_path = fallback_dir / f"{slug}.zip"
                    with zipfile.ZipFile(
                        zip_path,
                        mode="w",
                        compression=zipfile.ZIP_DEFLATED,
                    ) as archive:
                        archive.writestr(
                            f"{slug}/Borrador completo.txt",
                            "\n".join(complete_text),
                        )
                    download_status.value = f"ZIP guardado en app: {zip_path}"
                except OSError as error:
                    download_status.value = f"No se pudo crear el ZIP: {error}"
            download_status.update()

        page_navigation = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "← Anterior",
                    disabled=(current_page == 0),
                    on_click=lambda e: navigate_page(-1),
                ),
                ft.Text(
                    f"Hoja {current_page + 1} de {len(active_project['pages'])}",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.ElevatedButton(
                    "Siguiente →",
                    disabled=(current_page >= len(active_project["pages"]) - 1),
                    on_click=lambda e: navigate_page(1),
                ),
                ft.ElevatedButton(
                    "＋ Nueva hoja",
                    on_click=add_page,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
        )

        page.add(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                "← Proyectos",
                                on_click=show_projects,
                            ),
                            status_text,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Text(
                        "Editor de novela",
                        size=30,
                        weight=ft.FontWeight.BOLD,
                    ),
                    title_input,
                    ft.Text("Modo de escritura"),
                    toolbar,
                    margin_controls,
                    font_control,
                    ft.Container(
                        content=paper,
                        alignment=ft.Alignment.CENTER,
                        padding=12,
                    ),
                    page_navigation,
                    ft.Row(
                        controls=[
                            ft.Text(
                                f"{project_character_count(active_project)} "
                                "caracteres en el proyecto",
                                size=11,
                            ),
                            ft.ElevatedButton(
                                "Descargar ZIP",
                                icon=ft.Icons.DOWNLOAD,
                                on_click=export_zip,
                            ),
                            ft.ElevatedButton(
                                "Ajustes",
                                on_click=show_settings,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    download_status,
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )
        )

    def navigate_page(change):
        nonlocal current_page
        if not active_project:
            return
        next_page = current_page + change
        if 0 <= next_page < len(active_project["pages"]):
            current_page = next_page
            active_project["current_page"] = current_page
            persist_project()
            show_editor()

    def add_page(_=None):
        nonlocal current_page
        if not active_project:
            return
        active_project["pages"].append(empty_page())
        current_page = len(active_project["pages"]) - 1
        active_project["current_page"] = current_page
        persist_project()
        show_editor()

    show_home()


ft.app(target=main)
      
