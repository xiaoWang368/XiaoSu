"""mock_api 接口测试(无 LLM / 无外部依赖)。"""

from fastapi.testclient import TestClient

from mock_api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_employee_001_technical_dept():
    """Q4:员工 001 是哪个部门的?→ /api/employee/001。"""
    r = client.get("/api/employee/001")
    assert r.status_code == 200
    data = r.json()
    assert data["dept"] == "技术部"


def test_orders_non_empty():
    """Q5:上周一共多少订单?→ /api/orders(确定性生成,count>0)。"""
    r = client.get("/api/orders")
    assert r.status_code == 200
    assert r.json()["count"] > 0
    assert r.json()["total_amount"] > 0


def test_attendance_work_days():
    """考勤接口:工作日有出勤。"""
    r = client.get("/api/attendance", params={"emp_id": "001"})
    assert r.status_code == 200
    assert r.json()["work_days"] > 0
