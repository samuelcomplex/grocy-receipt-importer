from pathlib import Path

from pypdf import PdfReader

from plugins.ica import ICAParser


PDF_PATH = Path("/tmp/ica-test.pdf")


def test_ica_parser_layout_pdf():
    reader = PdfReader(str(PDF_PATH))

    text = "\n".join(
        page.extract_text(extraction_mode="layout") or ""
        for page in reader.pages
    )

    result = ICAParser().parse(text)

    print("\nLAYOUT PARSER RESULT")
    print("metadata:", result["metadata"])

    for item in result["items"]:
        print("item:", item)

    assert result["items"]
