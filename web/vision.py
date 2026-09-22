from pathlib import Path

import cv2
import numpy as np
import qrcode

WIDTH, HEIGHT = 1200, 760
LOCATIONS = ["A01", "A02", "B01", "B02", "C01", "C02"]
EXPECTED = {"A01": ("PAL-001", 8), "A02": ("PAL-002", 6), "B01": ("PAL-003", 10),
            "B02": ("PAL-004", 5), "C01": ("PAL-005", 7), "C02": ("PAL-006", 9)}


def _qr(payload, size=106):
    image = qrcode.make(payload).convert("RGB").resize((size, size))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _scenario_data(scenario):
    data = dict(EXPECTED)
    if scenario in ("discrepancy", "blurred", "rescan"):
        data["B01"] = ("PAL-009", 10)
        data["C01"] = ("EMPTY", 0)
    return data


def create_demo_image(output, scenario):
    image=np.full((HEIGHT,WIDTH,3),(247,249,250),np.uint8)
    cv2.rectangle(image,(0,0),(WIDTH,92),(54,47,24),-1)
    cv2.putText(image,"AEROTWIN IQ ADAPTIVE - BODEGA SIMULADA",(42,42),cv2.FONT_HERSHEY_SIMPLEX,.95,(255,255,255),2,cv2.LINE_AA)
    cv2.putText(image,"QR demo: ubicacion + pallet | La operacion real conservaria el barcode del pallet",(43,72),cv2.FONT_HERSHEY_SIMPLEX,.52,(210,235,232),1,cv2.LINE_AA)
    data=_scenario_data(scenario)
    for idx,code in enumerate(LOCATIONS):
        col,row=idx%3,idx//3; x=35+col*390; y=120+row*305
        cv2.rectangle(image,(x,y),(x+350,y+270),(41,132,123),3)
        cv2.rectangle(image,(x+3,y+3),(x+347,y+55),(229,240,240),-1)
        pallet,qty=data[code]
        cv2.putText(image,f"{code} | {pallet}",(x+15,y+37),cv2.FONT_HERSHEY_SIMPLEX,.68,(30,54,72),2,cv2.LINE_AA)
        payload=f"LOC:{code}|PAL:{pallet}|QTY:{qty}"
        qr=_qr(payload); image[y+72:y+178,x+18:x+124]=qr
        cv2.putText(image,f"Cantidad: {qty}",(x+145,y+118),cv2.FONT_HERSHEY_SIMPLEX,.72,(30,54,72),2,cv2.LINE_AA)
        cv2.putText(image,"Evidencia visual simulada",(x+145,y+151),cv2.FONT_HERSHEY_SIMPLEX,.45,(80,95,105),1,cv2.LINE_AA)
        for n in range(min(qty,10)):
            bx=x+145+(n%5)*36; by=y+174+(n//5)*38
            cv2.rectangle(image,(bx,by),(bx+28,by+30),(48,132,195),-1)
    if scenario=="blurred": image=cv2.GaussianBlur(image,(25,25),9)
    cv2.imwrite(str(output),image)


def create_demo_images(folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    create_demo_image(folder/"01_inventario_correcto.png","initial")
    create_demo_image(folder/"02_lectura_borrosa_rescan.png","blurred")
    create_demo_image(folder/"03_rescan_resuelto.png","rescan")


def decode_image(data):
    image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
    if image is None: raise ValueError("No se pudo leer la imagen seleccionada.")
    return cv2.resize(image,(WIDTH,HEIGHT))


def image_quality(image):
    variance=cv2.Laplacian(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var()
    score=max(20,min(99,round(variance/9)))
    return score,variance


def analyze_image(image):
    image=cv2.resize(image,(WIDTH,HEIGHT)); quality,_=image_quality(image); annotated=image.copy(); readings={}
    detector=cv2.QRCodeDetector()
    # En el escenario controlado cada celda se analiza por separado. Esto evita
    # perder un código cuando existen varios QR en la misma fotografía.
    for idx, expected_code in enumerate(LOCATIONS):
        col,row=idx%3,idx//3; x=35+col*390; y=120+row*305
        crop=image[y+58:y+195,x+5:x+145]
        payload,points,_=detector.detectAndDecode(crop)
        if not payload: continue
        parts=dict(piece.split(":",1) for piece in payload.split("|") if ":" in piece)
        code=parts.get("LOC")
        if code in LOCATIONS:
            readings[code]={"pallet":parts.get("PAL","NO-LEIDO"),"qty":int(parts.get("QTY",0)),"confidence":quality}
            if points is not None:
                pts=np.int32(points).reshape(-1,2); pts[:,0]+=x+5; pts[:,1]+=y+58
                cv2.polylines(annotated,[pts],True,(40,160,80),4)
    # La baja calidad es una decisión explícita; no se inventan códigos faltantes.
    if quality < 70:
        readings={}
        cv2.putText(annotated,"BAJA CONFIANZA - RESCAN REQUERIDO",(275,380),cv2.FONT_HERSHEY_SIMPLEX,1.1,(40,40,210),3,cv2.LINE_AA)
    return readings,annotated,quality
