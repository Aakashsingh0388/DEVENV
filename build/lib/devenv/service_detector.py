"""
service_detector.py -- Detect required external services for a project.

Responsibility:
    Scan the project to identify external services that the application
    depends on, such as databases (PostgreSQL, MySQL, MongoDB), caches
    (Redis), message queues (Kafka, RabbitMQ), and other infrastructure.

Detection strategies:
    1. **docker-compose.yml** - Parse service definitions to find database
       images, Redis, Kafka, etc.
    2. **Environment variables** - Look for patterns like DATABASE_URL,
       REDIS_URL, MONGODB_URI in .env files and templates.
    3. **Framework defaults** - Some frameworks have conventional dependencies
       (e.g., Rails often uses PostgreSQL).
    4. **Dependency files** - Check for database drivers in package.json,
       requirements.txt, etc.

This module provides the infrastructure detection used by the ``doctor``
and ``info`` commands to show a complete picture of project requirements.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

# Service name -> detection patterns
SERVICE_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "PostgreSQL": {
        "docker_images": ["postgres", "postgresql", "timescale"],
        "env_patterns": [
            r"POSTGRES",
            r"PG_",
            r"DATABASE_URL.*postgres",
            r"PGHOST",
            r"PGUSER",
            r"PGPASSWORD",
            r"PGDATABASE",
        ],
        "npm_packages": [
            "pg", "pg-promise", "postgres", "typeorm", "prisma",
            "@prisma/client", "knex", "sequelize", "drizzle-orm",
            "@neondatabase/serverless",
        ],
        "pip_packages": [
            "psycopg2", "psycopg2-binary", "psycopg", "asyncpg",
            "sqlalchemy", "databases", "django", "tortoise-orm",
        ],
    },
    "MySQL": {
        "docker_images": ["mysql", "mariadb", "percona"],
        "env_patterns": [
            r"MYSQL",
            r"MARIADB",
            r"DATABASE_URL.*mysql",
        ],
        "npm_packages": ["mysql", "mysql2", "typeorm", "knex", "sequelize"],
        "pip_packages": ["mysqlclient", "pymysql", "aiomysql", "mysql-connector-python"],
    },
    "MongoDB": {
        "docker_images": ["mongo", "mongodb"],
        "env_patterns": [
            r"MONGO",
            r"MONGODB_URI",
            r"DATABASE_URL.*mongodb",
        ],
        "npm_packages": ["mongodb", "mongoose", "mongoist"],
        "pip_packages": ["pymongo", "motor", "mongoengine", "beanie"],
    },
    "Redis": {
        "docker_images": ["redis", "keydb", "dragonfly"],
        "env_patterns": [
            r"REDIS",
            r"CACHE_URL.*redis",
            r"CELERY_BROKER.*redis",
        ],
        "npm_packages": ["redis", "ioredis", "@upstash/redis", "bullmq", "bull"],
        "pip_packages": ["redis", "aioredis", "celery", "fakeredis"],
    },
    "Kafka": {
        "docker_images": ["kafka", "confluentinc/cp-kafka", "bitnami/kafka"],
        "env_patterns": [
            r"KAFKA",
            r"KAFKA_BOOTSTRAP_SERVERS",
            r"KAFKA_BROKER",
        ],
        "npm_packages": ["kafkajs", "kafka-node", "@confluentinc/kafka-javascript"],
        "pip_packages": ["kafka-python", "aiokafka", "confluent-kafka", "faust"],
    },
    "RabbitMQ": {
        "docker_images": ["rabbitmq"],
        "env_patterns": [
            r"RABBITMQ",
            r"AMQP_URL",
            r"CELERY_BROKER.*amqp",
        ],
        "npm_packages": ["amqplib", "amqp-connection-manager", "rascal"],
        "pip_packages": ["pika", "aio-pika", "kombu", "celery"],
    },
    "Elasticsearch": {
        "docker_images": ["elasticsearch", "opensearch"],
        "env_patterns": [
            r"ELASTICSEARCH",
            r"ELASTIC_",
            r"OPENSEARCH",
            r"ES_HOST",
        ],
        "npm_packages": ["@elastic/elasticsearch", "elasticsearch", "@opensearch-project/opensearch"],
        "pip_packages": ["elasticsearch", "opensearch-py", "elasticsearch-dsl"],
    },
    "MinIO": {
        "docker_images": ["minio"],
        "env_patterns": [
            r"MINIO",
            r"S3_ENDPOINT.*minio",
            r"AWS_ENDPOINT.*minio",
        ],
        "npm_packages": ["minio", "@aws-sdk/client-s3"],
        "pip_packages": ["minio", "boto3"],
    },
    "Memcached": {
        "docker_images": ["memcached"],
        "env_patterns": [
            r"MEMCACHED",
            r"MEMCACHE_",
        ],
        "npm_packages": ["memcached", "memjs"],
        "pip_packages": ["pymemcache", "python-memcached"],
    },
}


@dataclass
class ServiceInfo:
    """
    Information about a detected service dependency.

    Attributes
    ----------
    name:
        Human-readable service name (e.g., "PostgreSQL").
    detected_via:
        How the service was detected (e.g., "docker-compose.yml", "environment variables").
    details:
        Additional context about the detection.
    required:
        Whether this service is definitively required vs. optional/detected.
    """
    name: str
    detected_via: str
    details: str = ""
    required: bool = True


@dataclass
class ServiceDetectionResult:
    """
    Complete result of service detection for a project.

    Attributes
    ----------
    services:
        List of detected services.
    docker_services:
        Services found in docker-compose files.
    env_services:
        Services detected from environment variables.
    dependency_services:
        Services detected from package dependencies.
    """
    services: List[ServiceInfo] = field(default_factory=list)
    docker_services: Set[str] = field(default_factory=set)
    env_services: Set[str] = field(default_factory=set)
    dependency_services: Set[str] = field(default_factory=set)

    @property
    def all_service_names(self) -> Set[str]:
        """Return unique set of all detected service names."""
        return {s.name for s in self.services}

    @property
    def has_services(self) -> bool:
        """True if any services were detected."""
        return len(self.services) > 0


def _parse_docker_compose(compose_path: Path) -> List[str]:
    """
    Parse a docker-compose file and extract image names.
    
    Returns a list of image names found in the services section.
    """
    images: List[str] = []
    
    try:
        content = compose_path.read_text(encoding="utf-8", errors="ignore")
        
        # Simple regex-based parsing for image: directives
        # This avoids requiring PyYAML as a dependency
        image_pattern = re.compile(r"^\s*image:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
        matches = image_pattern.findall(content)
        images.extend(matches)
        
        # Also check for service names that might indicate the service type
        service_pattern = re.compile(r"^\s+(\w+):\s*$", re.MULTILINE)
        service_names = service_pattern.findall(content)
        
        # Common service name conventions
        service_name_map = {
            "db": "postgres",
            "database": "postgres",
            "postgres": "postgres",
            "postgresql": "postgres",
            "mysql": "mysql",
            "mariadb": "mariadb",
            "mongo": "mongo",
            "mongodb": "mongo",
            "redis": "redis",
            "cache": "redis",
            "kafka": "kafka",
            "zookeeper": "zookeeper",
            "rabbitmq": "rabbitmq",
            "rabbit": "rabbitmq",
            "elasticsearch": "elasticsearch",
            "elastic": "elasticsearch",
            "minio": "minio",
        }
        
        for svc in service_names:
            svc_lower = svc.lower()
            if svc_lower in service_name_map:
                images.append(service_name_map[svc_lower])
                
    except (OSError, IOError):
        pass
    
    return images


def _scan_env_files(project_root: Path) -> List[str]:
    """
    Scan environment files for service-related variables.
    
    Returns a list of environment variable names and values found.
    """
    env_content: List[str] = []
    
    env_files = [
        ".env",
        ".env.example",
        ".env.sample",
        ".env.template",
        ".env.local",
        ".env.development",
        ".env.production",
    ]
    
    for env_file in env_files:
        env_path = project_root / env_file
        if env_path.is_file():
            try:
                content = env_path.read_text(encoding="utf-8", errors="ignore")
                env_content.append(content)
            except (OSError, IOError):
                pass
    
    return env_content


def _scan_package_json(project_root: Path) -> Set[str]:
    """
    Extract dependency names from package.json.
    """
    packages: Set[str] = set()
    package_json = project_root / "package.json"
    
    if not package_json.is_file():
        return packages
    
    try:
        content = package_json.read_text(encoding="utf-8", errors="ignore")
        
        # Simple regex extraction for dependencies
        # Matches: "package-name": "version"
        dep_pattern = re.compile(r'"([^"@][^"]*)":\s*"[^"]*"')
        
        # Find dependencies and devDependencies sections
        in_deps = False
        brace_count = 0
        
        for line in content.split("\n"):
            if '"dependencies"' in line or '"devDependencies"' in line:
                in_deps = True
                brace_count = 0
            
            if in_deps:
                brace_count += line.count("{") - line.count("}")
                matches = dep_pattern.findall(line)
                packages.update(matches)
                
                if brace_count <= 0 and "{" in line:
                    in_deps = False
                    
    except (OSError, IOError):
        pass
    
    return packages


def _scan_requirements_txt(project_root: Path) -> Set[str]:
    """
    Extract package names from requirements.txt and similar files.
    """
    packages: Set[str] = set()
    
    req_files = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-prod.txt",
        "requirements/base.txt",
        "requirements/dev.txt",
        "requirements/prod.txt",
    ]
    
    for req_file in req_files:
        req_path = project_root / req_file
        if req_path.is_file():
            try:
                content = req_path.read_text(encoding="utf-8", errors="ignore")
                for line in content.split("\n"):
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # Extract package name (before version specifier)
                    match = re.match(r"^([a-zA-Z0-9_-]+)", line)
                    if match:
                        packages.add(match.group(1).lower())
            except (OSError, IOError):
                pass
    
    # Also check pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            # Simple extraction of dependencies
            dep_pattern = re.compile(r'"([a-zA-Z0-9_-]+)')
            if "dependencies" in content:
                packages.update(dep_pattern.findall(content))
        except (OSError, IOError):
            pass
    
    return packages


def detect_services(project_root: Path) -> ServiceDetectionResult:
    """
    Scan the project and detect required external services.
    
    Parameters
    ----------
    project_root:
        Path to the project directory to scan.
    
    Returns
    -------
    ServiceDetectionResult:
        Complete information about detected services.
    """
    result = ServiceDetectionResult()
    detected: Dict[str, ServiceInfo] = {}
    
    # ── 1. Check docker-compose files ───────────────────────────────
    compose_files = [
        project_root / "docker-compose.yml",
        project_root / "docker-compose.yaml",
        project_root / "compose.yml",
        project_root / "compose.yaml",
    ]
    
    docker_images: List[str] = []
    for compose_file in compose_files:
        if compose_file.is_file():
            docker_images.extend(_parse_docker_compose(compose_file))
    
    for service_name, patterns in SERVICE_PATTERNS.items():
        for image in docker_images:
            image_lower = image.lower()
            for pattern in patterns.get("docker_images", []):
                if pattern in image_lower:
                    result.docker_services.add(service_name)
                    if service_name not in detected:
                        detected[service_name] = ServiceInfo(
                            name=service_name,
                            detected_via="docker-compose",
                            details=f"Image: {image}",
                            required=True,
                        )
                    break
    
    # ── 2. Check environment files ──────────────────────────────────
    env_contents = _scan_env_files(project_root)
    combined_env = "\n".join(env_contents)
    
    for service_name, patterns in SERVICE_PATTERNS.items():
        for pattern in patterns.get("env_patterns", []):
            if re.search(pattern, combined_env, re.IGNORECASE):
                result.env_services.add(service_name)
                if service_name not in detected:
                    detected[service_name] = ServiceInfo(
                        name=service_name,
                        detected_via="environment variables",
                        details=f"Pattern: {pattern}",
                        required=True,
                    )
                break
    
    # ── 3. Check package dependencies ───────────────────────────────
    npm_packages = _scan_package_json(project_root)
    pip_packages = _scan_requirements_txt(project_root)
    
    for service_name, patterns in SERVICE_PATTERNS.items():
        # Check npm packages
        for pkg in patterns.get("npm_packages", []):
            if pkg in npm_packages:
                result.dependency_services.add(service_name)
                if service_name not in detected:
                    detected[service_name] = ServiceInfo(
                        name=service_name,
                        detected_via="npm dependency",
                        details=f"Package: {pkg}",
                        required=True,
                    )
                break
        
        # Check pip packages
        for pkg in patterns.get("pip_packages", []):
            if pkg.lower() in pip_packages:
                result.dependency_services.add(service_name)
                if service_name not in detected:
                    detected[service_name] = ServiceInfo(
                        name=service_name,
                        detected_via="pip dependency",
                        details=f"Package: {pkg}",
                        required=True,
                    )
                break
    
    # Build final services list
    result.services = list(detected.values())
    
    return result


def get_service_summary(result: ServiceDetectionResult) -> str:
    """
    Generate a human-readable summary of detected services.
    """
    if not result.has_services:
        return "No external services detected."
    
    service_names = sorted(result.all_service_names)
    return f"This project appears to require: {', '.join(service_names)}"
