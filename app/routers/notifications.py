from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas import NotificationOut
from app.auth import require_role
from app.database import get_db
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])

def create_notification(db: Session, user_id: int, title: str, message: str, type: str = "info"):
    """Função helper para criar notificações"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type
    )
    db.add(notification)
    db.commit()
    return notification

@router.get("/", response_model=List[NotificationOut])
def get_notifications(
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    notifications = db.query(Notification).filter(
        Notification.user_id == int(current_user["sub"])
    ).order_by(Notification.created_at.desc()).all()
    
    return notifications

@router.get("/unread", response_model=List[NotificationOut])
def get_unread_notifications(
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    notifications = db.query(Notification).filter(
        Notification.user_id == int(current_user["sub"]),
        Notification.read == False
    ).order_by(Notification.created_at.desc()).all()
    
    return notifications

@router.patch("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == int(current_user["sub"])
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    
    notification.read = True
    db.commit()
    
    return {"message": "Notificação marcada como lida"}

@router.patch("/read-all")
def mark_all_as_read(
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == int(current_user["sub"]),
        Notification.read == False
    ).update({"read": True})
    
    db.commit()
    
    return {"message": "Todas as notificações marcadas como lidas"}

@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == int(current_user["sub"])
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    
    db.delete(notification)
    db.commit()
    
    return {"message": "Notificação excluída"}
