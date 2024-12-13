
# Xero Report API

A Django-based REST API service that integrates with Xero's API to generate account balance reports for specific account types. Built with Django 5, Django REST Framework, and PostgreSQL.

---

## **Features**

- **JWT Authentication**
- **Xero API Calls**
- **Report Generation**: Create reports for specific periods and account types.
- **Database Persistence**: Store and retrieve reports in PostgreSQL.

---

## **Prerequisites**

- Docker and Docker Compose
- Python 3.10+
- PostgreSQL 13+
- A Xero Developer account with API credentials

---

## **Quick Start**

1. **Clone the repository**:
   ```bash
   git clone https://github.com/thomasmacdo/XeroReports.git
   cd XeroReports
   ```

2. **Set up the environment**:
   Rename the `.example.env` to `.env` file at the project root and configure the required environment variables:
   ```env
   DEBUG=1
   SECRET_KEY=<django-secret-key>
   DJANGO_SETTINGS_MODULE=core.settings
   SQL_ENGINE=django.db.backends.postgresql
   SQL_DATABASE=xero_db
   SQL_USER=xero_user
   SQL_PASSWORD=xero_password
   SQL_HOST=db
   SQL_PORT=5432
   XERO_CLIENT_ID=<xero-client-id>
   XERO_SECRET_KEY=<xero-secret-key>
   ```

3. **Set up the virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Generate SSL Certificates**:
   Ensure you have `mkcert` installed, then run:
   ```bash
   chmod +x scripts/generate_certs.sh
   ./scripts/generate_certs.sh
   ```
   Certificates will be created in the `certs` directory and automatically mounted in the Docker container.

5. **Run the application using Docker**:
   ```bash
   docker compose up -d --build
   ```

6. **Apply database migrations**:
   ```bash
   ./scripts/manage.sh migrate
   ```

7. **Access the API**:
   - The application will be available at: [https://localhost](https://localhost)

8. **Create a superuser**:
   ```bash
   ./scripts/manage.sh createsuperuser
   ```

---

## **Run Tests**
   ```bash
   ./scripts/run_tests.sh
   ```

---

## **API Usage Guide**

### 1. Login to Get JWT Token
   ```bash
   curl -X POST https://localhost/api/token/ \
   -H "Content-Type: application/json" \
   -d '{
       "username": "user",
       "password": "password"
     }'
   ```

### 2. Get Xero Authorization URL
   ```bash
   curl -X GET https://localhost/xero/connect/ \
   -H "Authorization: Bearer <access_token>"
   ```

### 3. Generate a Report
   ```bash
   curl -X POST https://localhost/reports/generate/ \
   -H "Authorization: Bearer <access_token>" \
   -H "Content-Type: application/json" \
   -d '{
       "period": "Jan-2024",
       "account_type": "REVENUE",
       "tenant_name": "Demo Company (UK)"
     }'
   ```

### 4. Get All Reports
   ```bash
   curl -X GET https://localhost/reports/ \
   -H "Authorization: Bearer <access_token>"
   ```

### 5. Get Report Details
   ```bash
   curl -X GET https://localhost/reports/<report_id>/details/ \
   -H "Authorization: Bearer <access_token>"
   ```

---

## **Future Improvements**
- Add integration tests to improve coverage.
- Implement a mock Xero API server for local testing, such as using [Mockoon](https://github.com/mockoon/mockoon).
- Upgrade the version of postgres that this project is using.
- Migrate to use poetry over pip.