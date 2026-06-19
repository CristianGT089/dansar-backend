# Importar todos los modelos aquí para que Alembic y SQLAlchemy
# los detecten al arrancar, sin importar el orden de carga.
from app.modules.companies.models import Company  # noqa: F401
from app.modules.users.models import RefreshToken, User, UserCompanyRole  # noqa: F401
from app.modules.plans.models import (  # noqa: F401
    CompanyFeature,
    CompanyPlan,
    Feature,
    Plan,
)
