"""
小苏内部系统 Mock 服务(端口 8001):员工 / 考勤 / 订单,确定性生成。

数据只由「日期 + 员工ID」决定,同一天重复查询结果一致;覆盖全年任意时间段,
缺省取最近一个自然周(考勤)/ 最近 7 天(订单),方便面试题"上周"之类的问题。
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException

app = FastAPI(title="小苏 Mock 内部系统", version="0.1.0")

EMPLOYEES = {
    "001": {"id": "001", "name": "张三", "dept": "技术部", "title": "后端工程师", "hire_date": "2022-03-15"},
    "002": {"id": "002", "name": "李四", "dept": "市场部", "title": "市场专员", "hire_date": "2023-01-10"},
    "003": {"id": "003", "name": "王五", "dept": "人事部", "title": "HR专员", "hire_date": "2021-08-01"},
    "004": {"id": "004", "name": "赵六", "dept": "财务部", "title": "会计", "hire_date": "2020-06-20"},
    "005": {"id": "005", "name": "孙七", "dept": "销售部", "title": "销售经理", "hire_date": "2019-11-05"},
}


def _rng(*seeds: str) -> random.Random:
    h = hashlib.md5(":".join(seeds).encode()).hexdigest()[:8]
    return random.Random(int(h, 16))


def _recent_week() -> tuple[date, date]:
    """最近一个完整自然周(周一~周日)。"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def _parse_date(s: str | None, default: date) -> date:
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/employee/{emp_id}")
def get_employee(emp_id: str):
    emp = EMPLOYEES.get(emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="员工不存在")
    return emp


@app.get("/api/attendance")
def get_attendance(emp_id: str, start: str | None = None, end: str | None = None):
    if emp_id not in EMPLOYEES:
        raise HTTPException(status_code=404, detail="员工不存在")
    start_d = _parse_date(start, _recent_week()[0])
    end_d = _parse_date(end, _recent_week()[1])
    days = []
    d = start_d
    while d <= end_d:
        r = _rng(emp_id, d.isoformat())
        if d.weekday() < 5:
            status = "normal" if r.random() > 0.05 else "leave"
        else:
            status = "off"
        days.append({"date": d.isoformat(), "status": status})
        d += timedelta(days=1)
    return {
        "emp_id": emp_id,
        "days": days,
        "work_days": sum(1 for x in days if x["status"] == "normal"),
        "total_days": len(days),
    }


@app.get("/api/orders")
def get_orders(start: str | None = None, end: str | None = None):
    end_d = date.today()
    start_d = _parse_date(start, end_d - timedelta(days=6))
    end_d = _parse_date(end, end_d)
    orders = []
    total_amount = 0.0
    d = start_d
    while d <= end_d:
        r = _rng("orders", d.isoformat())
        for _ in range(r.randint(10, 40)):
            amount = round(r.uniform(50, 5000), 2)
            total_amount += amount
            orders.append({
                "id": f"O{d:%Y%m%d}{r.randint(100, 999)}",
                "amount": amount,
                "date": d.isoformat(),
                "customer": f"客户{r.randint(1, 20)}",
            })
        d += timedelta(days=1)
    return {
        "count": len(orders),
        "total_amount": round(total_amount, 2),
        "orders": orders[:50],
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
    }
