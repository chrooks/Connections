# Backend Development Guidelines

## Stack

- **Language:** Python 3.6+
- **Framework:** Flask
- **Database:** SQLite (connectionsdb.db)
- **Virtual Environment:** `.venv/`

## Project Structure

```
/src/           - Main application code
/tests/         - Test files
/schemas/       - Database schemas
requirements.txt - Python dependencies
```

## Development Setup

### Environment Setup

1. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Fill in required environment variables
   - **Never commit `.env` to version control**

### Running the Server

```bash
python -m src.app
```

The server runs on `localhost:5000` by default.

## Code Style

### Python Standards

- **Follow PEP 8** - Standard Python style guide
- **Type hints** - Use where it improves clarity
- **Descriptive names** - Clear, explicit variable and function names
- **Comments** - Explain *why*, not *what* (code should be self-documenting for the "what")

### Flask Patterns

- **Route organization** - Group related routes logically
- **Error handling** - Return appropriate HTTP status codes
- **JSON responses** - Consistent response format for API endpoints
- **Blueprint usage** - If the app grows, use blueprints for organization

### Database

- **SQLite** - Lightweight database for local development
- **Schema location** - Database schema definitions in `/schemas/`
- **Migrations** - Document schema changes if making database modifications
- **Connection management** - Properly close connections, use context managers

## API Development

### Creating Endpoints

1. **RESTful conventions** - Follow REST principles
   - GET for retrieval
   - POST for creation
   - PUT/PATCH for updates
   - DELETE for removal

2. **Response format** - Consistent JSON structure
   ```python
   # Success
   {"status": "success", "data": {...}}

   # Error
   {"status": "error", "message": "Error description"}
   ```

3. **Status codes** - Use appropriate HTTP status codes
   - 200: Success
   - 201: Created
   - 400: Bad request
   - 404: Not found
   - 500: Server error

### Frontend Communication

- **CORS** - Ensure CORS is properly configured for frontend origin
- **JSON parsing** - Validate and sanitize incoming JSON data
- **Error messages** - Return helpful error messages for frontend display

## Game Logic

### Word Generation

- **LLM Integration** - Uses language models to generate words and connections
- **Validation** - Ensure generated content meets game requirements
- **Caching** - Consider caching generated games if appropriate

### Game State

- **State management** - Track game progress, mistakes, connections found
- **Data persistence** - Store game data in SQLite
- **User sessions** - Handle both authenticated and guest users

## Testing

### Running Tests

```bash
pytest
```

### Writing Tests

- **Test location** - All tests in `/tests/` directory
- **Coverage** - Test critical game logic and API endpoints
- **Test data** - Use fixtures for test data
- **Don't disable tests** - Fix failing tests, don't skip them

## Common Tasks

### Adding a New API Endpoint

1. Define the route in appropriate module under `/src/`
2. Implement the handler function
3. Add input validation
4. Return consistent JSON response
5. Update frontend if needed
6. Test the endpoint

### Modifying Game Logic

1. Locate the relevant module in `/src/`
2. Understand existing implementation
3. Make changes incrementally
4. Test thoroughly
5. Update database schema if needed

### Database Changes

1. Document current schema
2. Plan migration strategy
3. Update schema files in `/schemas/`
4. Test with existing data
5. Consider data migration for production

## Dependencies

### Adding New Dependencies

1. Install with pip: `pip install package-name`
2. Update requirements.txt: `pip freeze > requirements.txt`
3. Document why the dependency is needed
4. Ensure it's compatible with Python 3.6+

## Security

- **Input validation** - Always validate user input
- **SQL injection** - Use parameterized queries
- **Environment variables** - Keep secrets in `.env`, never in code
- **Authentication** - Integrate with frontend's Supabase auth
- **Error messages** - Don't expose sensitive information in errors

## Performance

- **Database queries** - Optimize queries, use indexes where appropriate
- **Caching** - Cache expensive operations (LLM generation)
- **Connection pooling** - Reuse database connections efficiently

## Debugging

- **Logging** - Use Python's logging module for debugging
- **Error tracing** - Include stack traces in development
- **Development mode** - Use Flask's debug mode locally
- **Production safety** - Disable debug mode in production

## Important Reminders

- **Virtual environment** - Always work within `.venv`
- **Environment variables** - Use `.env` for configuration
- **Test before commit** - Run tests and manual testing
- **API contracts** - Keep frontend informed of API changes
- **Python version** - Maintain compatibility with Python 3.6+
