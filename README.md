# Xero Report API

A Django-based REST API service that integrates with Xero's API to generate reports of the users account balances for specific account types. Built with Django 5, Django REST Framework, and PostgreSQL.

---

## **Features**

- **JWT Authentication**: Secure user access.
- **Asynchronous API Calls**: Interaction with Xero's API.
- **Report Generation**: Create reports for specific periods and account types.
- **Database Persistence**: Store and retrieve reports in PostgreSQL.
- **Comprehensive Testing**: Includes pytest and pytest-django.

---

## **Assumptions**

- The application will manage only **one Xero Tenant**, such as "Demo Company (UK)".
- Authentication to Xero will be set up for this tenant.

---

## **Prerequisites**

- Docker and Docker Compose
- Python 3.10+
- PostgreSQL 13+
- A Xero Developer account with API credentials

---

## **Quick Start**

1. **Clone the repository**:

2. **Set up the environment**:
   Rename the example `.env` file at the project root with the required environment variables:
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

3. **Set up virtual environment**
  ```bash
  python -m virtualenv venv
  source venv/bin/activate

  pip install -r requirements.txt
  ```

4. **SSL Certificate Setup** Make sure you have `mkcert` installed:
   ```bash
   # macOS
   brew install mkcert

   # Linux
   # Follow mkcert installation instructions for your distribution

   chmod +x scripts/generate_certs.sh
   ./scripts/generate_certs.sh
   ```

The certificates will be generated in the `certs` directory and will be automatically mounted in the Docker container.

5. **Run the application using Docker**:
   ```bash
   docker compose up --build
   ```

6. **Apply database migrations**:
   ```bash
   ./scripts/manage.sh migrate
   ```

7. **Access the API**:
   - The application will be available at: [https://localhost](https://localhost)

8. **Create a user**:
   ```bash
   ./scripts/manage.sh createsuperuser
   ```
   Follow the prompts to create your username and password.

---

## **Run tests**:
   ```bash
   ./scripts/runtests.sh
   ```

---

## **Notes**

- Ensure that the callback url in Xero is set to **https://localhost/xero/callback/**

## **API Usage Guide with curl**

### 1. **Login to Get JWT Token**
   ```bash
   curl -X POST https://localhost/api/token/ \
     -H "Content-Type: application/json" \
     -d '{
       "username": "example",
       "password": "example_password"
     }'
   ```

   **Expected Response**:
   ```json
   {
     "access": "<access_token>",
     "refresh": "<refresh_token>"
   }
   ```

### 2. **Get Xero Authorization URL**
   ```bash
   curl -X GET https://localhost/xero/connect/ \
     -H "Authorization: Bearer <access_token>"
   ```

   **Expected Response**:
   - A URL to authorize the application with Xero.

### 3. **Generate a Report**
   Period is expected to be in the format Jan-2024 or January-2024
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

   **Expected Response**:
   ```json
    {
      "id":1,
      "user":8,
      "period":"2024-01-01",
      "account_type":"REVENUE",
      "created_at":"2024-11-28T22:54:18.517814Z"
    }
   ```

### 4. **Get All Reports**
   ```bash
   curl -X GET https://localhost/reports/ \
     -H "Authorization: Bearer <access_token>"
   ```

   **Expected Response**:
   ```json
   [
     {
       "id": 1,
       "user": 8,
       "period": "2024-10",
       "account_type": "REVENUE",
       "created_at": "2024-11-28T12:34:56Z"
     }
   ]
   ```

### 5. **Get Report Details**
   ```bash
   curl -X GET https://localhost/reports/<report_id>/details/ \
     -H "Authorization: Bearer <access_token>"
   ```

   **Expected Response**:
   ```json
   {
     "id": 1,
     "user": 8,
     "period": "2024-01-01",
     "account_type": "REVENUE",
     "created_at": "2024-10-28T12:34:56Z",
     "account_balances": [
       {
         "account_name": "Account 1",
         "xero_account_id": "041378b3-dabc-4a73-8327-d615597fd680",
         "account_balance":"100.00"
       },
       {
         "account_name": "Account 2",
         "xero_account_id": "05155558b3-dabc-4a73-5678-d615597fd680",
         "account_balance":"20.00"
       }
     ]
   }
   ```

## Project Structure
  ```bash
  .
  ├── Dockerfile
  ├── README.md
  ├── apps
  │   ├── reports
  │   └── xero_api
  ├── cert.pem
  ├── core
  │   ├── __init__.py
  │   ├── __pycache__
  │   ├── asgi.py
  │   ├── local.py
  │   ├── management
  │   ├── middleware.py
  │   ├── settings.py
  │   ├── tests
  │   └── urls.py
  ├── docker-compose.yml
  ├── key.pem
  ├── manage.py
  ├── pyproject.toml
  ├── requirements.txt
  ├── scripts
      ├── manage.sh
      └── run_tests.sh
  ```

## Things I would do with more time

I haven't added much integration testing. Maybe creating a mock Xero Api server with https://github.com/mockoon/mockoon
