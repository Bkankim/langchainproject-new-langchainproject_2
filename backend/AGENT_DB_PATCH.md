# 나머지 에이전트 DB 저장 로직 추가 가이드

## segment_agent.py
1. import 추가: `from app.db.crud import append_message, create_session, get_session, save_task_result`
2. return 전에 추가:
```python
# 종합 보고서용 결과 데이터 구조화
result_data = {
    "product_name": context.product_name,
    "num_segments": len(context.segments),
    "segments": context.segments
}

# DB에 태스크 결과 저장
with get_db() as db:
    save_task_result(
        db,
        session_id=context.session_id,
        task_type="segment",
        result_data=result_data,
        product_name=context.product_name,
        html_path=context.html_path
    )
```

## review_agent.py
1. import 추가: `from app.db.crud import append_message, create_session, get_session, save_task_result`
2. return 전에 추가:
```python
# 종합 보고서용 결과 데이터 구조화
result_data = {
    "product_name": context.product_name,
    "total_reviews": context.sentiment_result.get("total_reviews"),
    "sentiment_distribution": context.sentiment_result.get("sentiment_distribution"),
    "average_score": context.sentiment_result.get("average_score"),
    "topics": context.topics,
    "summary": context.summary,
    "improvements": context.improvements_area
}

# DB에 태스크 결과 저장
with get_db() as db:
    save_task_result(
        db,
        session_id=context.session_id,
        task_type="review",
        result_data=result_data,
        product_name=context.product_name,
        pdf_path=context.pdf_path
    )
```

## competitor_agent.py
1. import 추가: `from app.db.crud import append_message, create_session, get_session, save_task_result`
2. return 전에 추가:
```python
# 종합 보고서용 결과 데이터 구조화
result_data = {
    "product_name": context.product_name,
    "competitors": context.competitors,
    "num_competitors": len(context.competitors) if context.competitors else 0
}

# DB에 태스크 결과 저장
with get_db() as db:
    save_task_result(
        db,
        session_id=context.session_id,
        task_type="competitor",
        result_data=result_data,
        product_name=context.product_name,
        pdf_path=context.pdf_path
    )
```

**NOTE:** 실제 구현 시 위 코드를 각 에이전트의 성공 return 직전에 추가하세요.
