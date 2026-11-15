from io import BytesIO
from pypdf import PdfReader,PdfWriter
from flask import abort


def sanitize_pdf(data,code):
    if len(data)>20*1024*1024 or not data.startswith(b'%PDF-'):abort(400,'Нужен PDF до 20 МБ.')
    try:
        reader=PdfReader(BytesIO(data))
        if reader.is_encrypted or not 1<=len(reader.pages)<=100:abort(400,'PDF должен быть без пароля, от 1 до 100 страниц.')
        writer=PdfWriter()
        for page in reader.pages:
            for key in ['/Annots','/Metadata','/AA','/PieceInfo']:
                if key in page:del page[key]
            writer.add_page(page)
        writer.add_metadata({'/Title':'Проект '+code,'/Author':'','/Creator':'HackFlow','/Subject':'Обезличенные материалы'})
        out=BytesIO();writer.write(out);return out.getvalue()
    except Exception as error:
        from werkzeug.exceptions import HTTPException
        if isinstance(error,HTTPException):raise
        abort(400,'PDF повреждён или не читается.')
