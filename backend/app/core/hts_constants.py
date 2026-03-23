"""
HTS Constants - Sprint 5.3 Final Lock

Defines the authoritative HTS version and enforces version validation.
"""

# Authoritative HTS Version (NEW_UUID from Sprint 5.3)
# This is the only valid version for production duty resolution.
AUTHORITATIVE_HTS_VERSION_ID = "792bb867-c549-4769-80ca-d9d1adc883a3"

# Deprecated versions (for reference only, not used for resolution)
DEPRECATED_VERSIONS = {
    # Old version without suffix_token_text metadata
    # Do not use for resolution
}

def validate_hts_version_id(hts_version_id: str) -> str:
    """
    Validate HTS version ID and return authoritative version if None.
    
    Args:
        hts_version_id: Version ID to validate (or None for default)
    
    Returns:
        Validated version ID (always returns AUTHORITATIVE_HTS_VERSION_ID)
    
    Raises:
        ValueError: If version ID is provided but not recognized
    """
    if hts_version_id is None:
        return AUTHORITATIVE_HTS_VERSION_ID
    
    if hts_version_id == AUTHORITATIVE_HTS_VERSION_ID:
        return hts_version_id
    
    if hts_version_id in DEPRECATED_VERSIONS:
        raise ValueError(
            f"HTS version {hts_version_id} is deprecated and cannot be used for resolution. "
            f"Use AUTHORITATIVE_HTS_VERSION_ID: {AUTHORITATIVE_HTS_VERSION_ID}"
        )
    
    # Unknown version - hard fail
    raise ValueError(
        f"Unknown HTS version ID: {hts_version_id}. "
        f"Only AUTHORITATIVE_HTS_VERSION_ID ({AUTHORITATIVE_HTS_VERSION_ID}) is supported. "
        f"If you need a different version, it must be added to DEPRECATED_VERSIONS or become the new authoritative version."
    )
