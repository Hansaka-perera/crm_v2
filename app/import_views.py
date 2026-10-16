from flask import flash, redirect, render_template, request, send_file, session, url_for
from flask_login import login_required

from app.excel_io import TEMPLATES, read_tabular, template_bytes


def send_template(kind, filename):
    buf = template_bytes(kind)
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def handle_import(kind, importer, success_endpoint, template_endpoint):
    fields = TEMPLATES[kind]
    if request.method == "POST" and request.form.get("step") == "commit":
        records = session.get("import_records") or []
        mapping = {field: request.form.get(f"map_{field}") for field in fields}
        duplicate = request.form.get("duplicate", "skip")
        created, updated, skipped, errors = importer(records, mapping, duplicate)
        session.pop("import_records", None)
        session.pop("import_headers", None)
        flash(
            f"Import finished: {created} created, {updated} updated, {skipped} skipped.",
            "success",
        )
        for err in errors[:20]:
            flash(err, "error")
        return redirect(url_for(success_endpoint))

    if request.method == "POST" and "file" in request.files:
        file = request.files["file"]
        if not file or not file.filename:
            flash("Choose an Excel or CSV file.", "error")
            return redirect(request.url)
        headers, records = read_tabular(file)
        if not records:
            flash("The file did not contain any data rows.", "error")
            return redirect(request.url)
        session["import_records"] = records[:2000]
        session["import_headers"] = headers
        return render_template(
            "import/map.html",
            kind=kind,
            fields=fields,
            headers=headers,
            preview=records[:8],
            count=len(records),
        )

    return render_template(
            "import/upload.html",
            kind=kind,
            fields=fields,
            template_url=url_for(template_endpoint),
        )
