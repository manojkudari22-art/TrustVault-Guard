from urllib.request import Request, build_opener

from app.documents.routes import NoRedirectHandler


def test_office_redirect_handler_rejects_redirects():
    handler = NoRedirectHandler()
    request = Request("http://localhost:8080/document.docx")

    redirected_request = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {"Location": "http://example.com/redirected.docx"},
        "http://example.com/redirected.docx",
    )

    assert redirected_request is None

    opener = build_opener(NoRedirectHandler())
    assert any(
        isinstance(item, NoRedirectHandler)
        for item in opener.handlers
    )
