import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).with_name("aerotwin.db")


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    try:
        yield conn; conn.commit()
    finally:
        conn.close()


def _seed_rows():
    soon=(date.today()+timedelta(days=22)).isoformat(); ok=(date.today()+timedelta(days=180)).isoformat()
    now=datetime.now().isoformat(timespec="seconds")
    return [
        ("A01","PAL-001","PAL-001","Nescafé Clásico","SKU-101","L260901",ok,8,8,"Alto","Disponible",7,14,1,"Alta",0,98,"Verificado",now),
        ("A02","PAL-002","PAL-002","La Lechera","SKU-102","L260902",ok,6,6,"Alto","Disponible",2,6,0,"Media",0,97,"Verificado",now),
        ("B01","PAL-003","PAL-003","Maggi Caldo","SKU-103","L260903",soon,10,10,"Alto","Disponible",12,28,2,"Alta",0,96,"Verificado",now),
        ("B02","PAL-004","PAL-004","Cereal Fitness","SKU-104","L260904",ok,5,5,"Bajo","Ocupado por montacargas",9,26,1,"Alta",0,95,"Verificado",now),
        ("C01","PAL-005","PAL-005","Nesquik","SKU-105","L260905",ok,7,7,"Bajo","Disponible",5,20,2,"Media",1,54,"ReScan",now),
        ("C02","PAL-006","PAL-006","KitKat","SKU-106","L260906",ok,9,9,"Bajo","Disponible",1,3,0,"Baja",0,99,"Verificado",now),
    ]


def init_db():
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS locations(code TEXT PRIMARY KEY,expected_pallet TEXT,current_pallet TEXT,product TEXT,sku TEXT,lot TEXT,expiry TEXT,expected_qty INTEGER,current_qty INTEGER,level TEXT,aisle_status TEXT,movements_24h INTEGER,hours_since_inspection REAL,anomaly_count INTEGER,turnover TEXT,pending_rescan INTEGER,confidence REAL,status TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS inspections(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,source TEXT,image_name TEXT,quality REAL,result TEXT,notes TEXT);
        CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT,inspection_id INTEGER,location_code TEXT,expected_pallet TEXT,observed_pallet TEXT,expected_qty INTEGER,observed_qty INTEGER,confidence REAL,outcome TEXT,message TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,location_code TEXT,task_type TEXT,priority TEXT,status TEXT,evidence TEXT);
        """)
        if conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] == 0:
            conn.executemany("INSERT INTO locations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",_seed_rows())


def _rows(query,params=()):
    with connection() as conn: return [dict(r) for r in conn.execute(query,params).fetchall()]
def get_locations(): return _rows("SELECT * FROM locations ORDER BY code")
def get_inspections(): return _rows("SELECT * FROM inspections ORDER BY id DESC")
def get_tasks(): return _rows("SELECT * FROM tasks ORDER BY id DESC")
def get_observations(limit=60): return _rows("SELECT * FROM observations ORDER BY id DESC LIMIT ?",(limit,))


def set_aisle_status(code,status):
    with connection() as conn: conn.execute("UPDATE locations SET aisle_status=? WHERE code=?",(status,code))


def create_task(code,task_type,priority,evidence=""):
    with connection() as conn:
        cur=conn.execute("INSERT INTO tasks(created_at,location_code,task_type,priority,status,evidence) VALUES(?,?,?,?,?,?)",(datetime.now().isoformat(timespec="seconds"),code,task_type,priority,"Pendiente",evidence))
        return cur.lastrowid


def close_task(task_id):
    with connection() as conn: conn.execute("UPDATE tasks SET status='Cerrada' WHERE id=?",(task_id,))


def register_inspection(observed,source,image_name,quality,notes=""):
    now=datetime.now().isoformat(timespec="seconds"); low=quality<70; result="ReScan requerido" if low else "Procesada"
    with connection() as conn:
        cur=conn.execute("INSERT INTO inspections(created_at,source,image_name,quality,result,notes) VALUES(?,?,?,?,?,?)",(now,source,image_name,quality,result,notes)); inspection_id=cur.lastrowid
        for loc in conn.execute("SELECT * FROM locations ORDER BY code").fetchall():
            item=observed.get(loc["code"],{}); pallet=item.get("pallet",loc["current_pallet"]); qty=int(item.get("qty",loc["current_qty"])); confidence=float(item.get("confidence",quality))
            if low or confidence<70:
                outcome="Evidencia insuficiente"; message="La lectura no supera el umbral. Se solicita otra captura."; pending=1; status="ReScan"
            elif pallet!=loc["expected_pallet"]:
                outcome="Pallet diferente"; message=f"WMS esperaba {loc['expected_pallet']} y se observó {pallet}."; pending=0; status="Excepción"
            elif qty!=loc["expected_qty"]:
                outcome="Cantidad diferente"; message=f"WMS esperaba {loc['expected_qty']} y se observaron {qty}."; pending=0; status="Excepción"
            else:
                outcome="Coincidencia"; message="Ubicación y pallet coinciden con el WMS simulado."; pending=0; status="Verificado"
            conn.execute("INSERT INTO observations(inspection_id,location_code,expected_pallet,observed_pallet,expected_qty,observed_qty,confidence,outcome,message) VALUES(?,?,?,?,?,?,?,?,?)",(inspection_id,loc["code"],loc["expected_pallet"],pallet,loc["expected_qty"],qty,confidence,outcome,message))
            if low:
                conn.execute("UPDATE locations SET confidence=?,pending_rescan=1,status='ReScan',updated_at=? WHERE code=?",(confidence,now,loc["code"]))
            else:
                conn.execute("UPDATE locations SET current_pallet=?,current_qty=?,confidence=?,pending_rescan=?,status=?,hours_since_inspection=0,updated_at=? WHERE code=?",(pallet,qty,confidence,pending,status,now,loc["code"]))
    return inspection_id,result


def reset_demo():
    with connection() as conn:
        conn.execute("DELETE FROM observations"); conn.execute("DELETE FROM inspections"); conn.execute("DELETE FROM tasks"); conn.execute("DELETE FROM locations")
        conn.executemany("INSERT INTO locations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",_seed_rows())
