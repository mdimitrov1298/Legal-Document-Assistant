"""Small request helpers shared by API tests."""

from __future__ import annotations

API = "/api/v1"

CONTRACT_TEXT = (
    "ДОГОВОР ЗА ПРЕДОСТАВЯНЕ НА УСЛУГИ. Възложителят заплаща на изпълнителя "
    "възнаграждение в размер на 4500 лв. без ДДС. Срокът за изпълнение е 30 дни "
    "от подписването на договора. Договорът е подписан в гр. Пловдив."
)


def create_case(client, title: str = "Демо дело", description: str | None = None):
    r = client.post(f"{API}/cases", json={"title": title, "description": description})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(
    client,
    case_id: str,
    name: str = "dogovor.txt",
    data: bytes | None = None,
    content_type: str = "text/plain",
):
    payload = CONTRACT_TEXT.encode() if data is None else data
    return client.post(
        f"{API}/cases/{case_id}/documents",
        files={"file": (name, payload, content_type)},
    )


def ingest(client, case_id: str) -> dict:
    r = client.post(f"{API}/cases/{case_id}/ingest")
    assert r.status_code == 200, r.text
    return r.json()
