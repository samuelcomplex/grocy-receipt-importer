from fastapi.templating import Jinja2Templates

from app.config import DEFAULT_LANGUAGE, TRANSLATIONS_DIR


templates = Jinja2Templates(directory="templates")


def load_translations():
    import json

    translations = {}

    for path in TRANSLATIONS_DIR.glob("*.json"):
        try:
            translations[path.stem] = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

    if DEFAULT_LANGUAGE not in translations:
        translations[DEFAULT_LANGUAGE] = {}

    return translations


TRANSLATIONS = load_translations()


def translate(key, language=DEFAULT_LANGUAGE):
    language_data = TRANSLATIONS.get(language, {})
    default_data = TRANSLATIONS.get(DEFAULT_LANGUAGE, {})

    return language_data.get(
        key,
        default_data.get(key, key),
    )


def get_language(request):
    language = request.cookies.get("language", DEFAULT_LANGUAGE)

    if language not in TRANSLATIONS:
        return DEFAULT_LANGUAGE

    return language


def render_template(request, template_name, context=None):
    context = dict(context or {})
    language = get_language(request)

    context["language"] = language
    context["available_languages"] = sorted(TRANSLATIONS)

    def request_translate(key):
        return translate(key, language)

    context["t"] = request_translate

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )
