from pydantic import BaseModel, Extra


class BaseSandboxConfig(BaseModel):
    """Common fields for any sandbox. Pure configuration schema."""

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
