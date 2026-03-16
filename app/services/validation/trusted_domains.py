# ==============================================================================
# app/services/validation/trusted_domains.py
# ==============================================================================
# Mapping of equipment manufacturers to their OFFICIAL trusted domains
# Only specs from these domains are accepted in PASS 4 cross-validation
# ==============================================================================

TRUSTED_DOMAINS_MAP = {
    "SolarEdge": [
        "solaredge.com",
        "knowledge-center.solaredge.com"
    ],
    "Enphase": [
        "enphase.com",
        "enphaserenewables.com"
    ],
    "Tesla": [
        "tesla.com",
        "teslaenergy.com"
    ],
    "SMA": [
        "sma.de",
        "sma.com",
        "smausa.com"
    ],
    "Huawei": [
        "huawei.com",
        "e-huawei.com"
    ],
    "Fronius": [
        "fronius.com",
        "fronius-internationl.com"
    ],
    "ABB": [
        "abb.com",
        "abb.com/power-grids"
    ],
    "JA Solar": [
        "jasolar.com",
        "jaso.com"
    ],
    "Canadian Solar": [
        "canadiansolar.com"
    ],
    "LONGi": [
        "longi.com",
        "longigroup.com"
    ],
    "Trina": [
        "trinasolar.com",
        "trinablade.com"
    ],
    "Risen": [
        "risensolar.com",
        "risenstatus.com"
    ],
    "Jinko": [
        "jinkosolar.com",
        "jinkosolar.com.cn"
    ],
    "First Solar": [
        "firstsolar.com"
    ],
    "APsystems": [
        "apsystems.com"
    ],
    "Growatt": [
        "growatt.com"
    ],
    "Solis": [
        "sofarsolar.com",
        "sofarenergy.com"
    ],
    "LG Chem": [
        "lg.com",
        "lgchem.com"
    ],
    "BYD": [
        "byd.com",
        "bydglobal.com"
    ],
    "Generac": [
        "generac.com",
        "generacpro.com"
    ],
    "Goodwe": [
        "goodwe.com"
    ],
    "Staubli": [
        "staubli.com"
    ],
    "Eaton": [
        "eaton.com"
    ]
}

# Domains that are explicitly BLOCKED (untrusted sources)
BLOCKED_DOMAINS = [
    "energysage.com",
    "manualslib.com",
    "scribd.com",
    "alibaba.com",
    "aliexpress.com",
    "ebay.com",
    "amazon.com",
    "solar-electric.com",
    "sunwatts.com",
    "pvoutput.org"
]


def get_trusted_domains(manufacturer: str) -> list:
    """Get list of trusted domains for a manufacturer"""
    # Normalize manufacturer name
    normalized = manufacturer.strip().title()
    return TRUSTED_DOMAINS_MAP.get(normalized, [])


def is_trusted_source(url: str, manufacturer: str) -> bool:
    """
    Check if URL is from a trusted source for this manufacturer
    
    Args:
        url: Source URL to check
        manufacturer: Equipment manufacturer name
    
    Returns:
        True if URL is from trusted manufacturer domain
        False if URL is from blocked or untrusted domain
    """
    if not url:
        return False
    
    url_lower = url.lower()
    
    # Check if URL is from blocked domain
    for blocked_domain in BLOCKED_DOMAINS:
        if blocked_domain in url_lower:
            return False
    
    # Check if URL is from trusted manufacturer domain
    trusted_domains = get_trusted_domains(manufacturer)
    for trusted_domain in trusted_domains:
        if trusted_domain in url_lower:
            return True
    
    # If not explicitly trusted and not blocked, it's untrusted
    return False


def categorize_source(url: str, manufacturer: str) -> str:
    """
    Categorize source quality
    
    Returns:
        "trusted" - official manufacturer domain
        "blocked" - explicitly blocked domain
        "untrusted" - unknown/third-party domain
    """
    if not url:
        return "untrusted"
    
    url_lower = url.lower()
    
    # Check blocked first
    for blocked_domain in BLOCKED_DOMAINS:
        if blocked_domain in url_lower:
            return "blocked"
    
    # Check trusted
    trusted_domains = get_trusted_domains(manufacturer)
    for trusted_domain in trusted_domains:
        if trusted_domain in url_lower:
            return "trusted"
    
    return "untrusted"
