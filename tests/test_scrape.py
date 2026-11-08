"""OWNER: B. Local-source ingest (PDF and HTML saved by hand) on throwaway files, no network."""
import csv

import rag.scrape as scrape


def _write_pdf(path, text):
    """A one-page PDF with `text` in Helvetica, built by hand so the test needs no PDF writer."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


def _setup(tmp_path, monkeypatch, rows):
    sources, corpus = tmp_path / "sources", tmp_path / "corpus"
    sources.mkdir()
    corpus.mkdir()
    with (sources / "sources.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "title", "url", "published", "product", "publisher", "keep_lines_matching"])
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(scrape, "SOURCES_DIR", sources)
    monkeypatch.setattr(scrape, "SOURCES_LIST", sources / "sources.csv")
    monkeypatch.setattr(scrape, "CORPUS", corpus)
    return sources, corpus


def _row(file, keep=""):
    return {"file": file, "title": "T", "url": "https://example.org", "published": "2026-04-15",
            "product": "regulatory", "publisher": "MAS", "keep_lines_matching": keep}


def test_pdf_and_html_sources_become_corpus_files(tmp_path, monkeypatch):
    sources, corpus = _setup(tmp_path, monkeypatch, [_row("report.pdf"), _row("page.html")])
    _write_pdf(sources / "report.pdf", "Retail investors using margin face forced liquidation")
    (sources / "page.html").write_text(
        "<html><body><nav>Menu</nav><main><h1>Shares</h1><p>Some investors use margin financing.</p></main></body></html>"
    )
    rows = scrape.local_sources()
    assert [r["chunk_source_file"] for r in rows] == ["report.txt", "page.txt"]
    assert "forced liquidation" in (corpus / "report.txt").read_text()
    page = (corpus / "page.txt").read_text()
    assert "margin financing" in page and "Menu" not in page
    assert rows[0]["fetched_on"] == "2026-04-15" and rows[0]["product"] == "regulatory"


def test_missing_file_is_skipped(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, [_row("not-downloaded.pdf")])
    assert scrape.local_sources() == []
    assert "save it from https://example.org" in capsys.readouterr().out


def test_long_filings_keep_only_matching_lines(tmp_path, monkeypatch):
    sources, corpus = _setup(tmp_path, monkeypatch, [_row("filing.html", keep="margin financing")])
    (sources / "filing.html").write_text(
        "<html><body><p>Revenue grew.</p><p>Our margin financing business carries credit risk.</p></body></html>"
    )
    scrape.local_sources()
    assert (corpus / "filing.txt").read_text().strip() == "Our margin financing business carries credit risk."
