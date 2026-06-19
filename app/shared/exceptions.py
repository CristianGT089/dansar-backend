from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, resource: str = "Recurso"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} no encontrado")


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Acceso denegado"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "No autenticado"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Conflicto con recurso existente"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
