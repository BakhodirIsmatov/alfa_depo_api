from fastapi import Response


def report_response(content: bytes, media_type: str, filename: str, row_count: int) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Report-Row-Count": str(row_count),
        },
    )
