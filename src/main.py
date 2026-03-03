# src/main.py
import base64
import binascii
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from src.printer import print_raw
from src.document import document_to_escpos

app = FastAPI(title='PrinterAPI')


class PrintRequest(BaseModel):
    raw: str

    @field_validator('raw')
    @classmethod
    def must_be_valid_base64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f'invalid base64: {e}')
        return v


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/print')
def print_ticket(req: PrintRequest):
    data = base64.b64decode(req.raw)
    try:
        print_raw(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'status': 'ok'}


class DocumentElement(BaseModel):
    model_config = {"extra": "allow"}
    type: str


class DocumentRequest(BaseModel):
    elements: list[DocumentElement]


@app.post('/print/document')
def print_document(req: DocumentRequest):
    data = document_to_escpos([el.model_dump() for el in req.elements])
    try:
        print_raw(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'status': 'ok'}
