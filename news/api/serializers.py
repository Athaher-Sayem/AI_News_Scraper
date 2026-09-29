import json


def _parse_json_field(value):
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value if value != "" else None


def serialize_article(item):
    scraped_date = item.scraped_date
    return {
        "id": item.pk,
        "source": item.source,
        "category": item.category,
        "title": item.title,
        "url": item.url,
        "content": item.content,
        "author": item.author,
        "published_date": item.published_date,
        "image_url": item.image_url,
        "language": item.language,
        "scraped_date": scraped_date.isoformat() if scraped_date else None,
    }


def serialize_processed(row, index):
    data = {
        "row": index,
        "source": row.get("source", ""),
        "category": row.get("category", ""),
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "content": row.get("content", ""),
        "author": row.get("author", ""),
        "published_date": row.get("published_date", ""),
        "image_url": row.get("image_url", ""),
        "language": row.get("language", ""),
        "scraped_date": row.get("scraped_date", ""),
        "status": row.get("status", ""),
        "reason": row.get("reason", ""),
        "generated_article": row.get("generated_article") or None,
        "facts": _parse_json_field(row.get("facts", "")),
        "verification": _parse_json_field(row.get("verification", "")),
    }
    return data


def serialize_job(job):
    return {
        "id": job.id,
        "status": job.status,
        "request": {
            "input": str(job.request.get("input_csv", "")),
            "output": str(job.request.get("output_csv", "")),
            "limit": job.request.get("limit"),
            "scrape": job.request.get("scrape", False),
            "deduplicate": job.request.get("deduplicate", False),
        },
        "summary": job.summary,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
