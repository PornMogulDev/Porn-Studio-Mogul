\# Session and Transaction Management Architecture



This document outlines the architectural patterns for managing database sessions and transactions across different services in the application. The core principle is the \*\*Session Factory Pattern\*\*, where each service is given a factory to create new sessions as needed, rather than sharing a single, long-lived session instance. This ensures clean separation, prevents state leakage, and improves stability.



Different types of services interact with the database in distinct ways, each with its own tailored session management pattern.



---



\## 1. Initialization Operations (`GameSessionService`)



\*\*Role:\*\* This service manages the game session lifecycle (new, load, save). It performs one-time, heavyweight setup operations.



\*\*Architecture:\*\*

This service creates and initializes game databases. It uses temporary sessions for initialization only, then closes them immediately. Future operations by other services will create their own sessions from the session factory.



\*\*Key Principles:\*\*

1\.  \*\*Use temporary sessions for initialization only\*\*: Initialization is a self-contained, transactional process.

2\.  \*\*Close initialization sessions immediately after commit\*\*: Once the initial state is written to the database, the session's job is done.

3\.  \*\*Services will create their own sessions later\*\*: The game controller receives the game state, and then initializes other services with a `session\_factory`, not a session instance.

4\.  \*\*Don't return session instances\*\*: The API is clean, returning only the necessary state (`GameState`, `save\_path`).

5\.  \*\*Use `try/except/finally` for proper cleanup\*\*: Guarantees rollback on error and session closure under all circumstances.



\*\*Correct Pattern Template:\*\*

```python

def initialize\_game(self) -> tuple\[GameState, str]:

&nbsp;   '''Initialize new game database.'''

&nbsp;   # Create database file

&nbsp;   save\_path = self.save\_manager.create\_new\_save\_db(name)

&nbsp;   

&nbsp;   # Create temporary session for initialization

&nbsp;   session = self.save\_manager.db\_manager.get\_session()

&nbsp;   try:

&nbsp;       # Perform all initialization

&nbsp;       session.add\_all(\[...])

&nbsp;       session.commit()

&nbsp;   except Exception as e:

&nbsp;       session.rollback()

&nbsp;       raise

&nbsp;   finally:

&nbsp;       session.close()  # ✅ Close initialization session

&nbsp;   

&nbsp;   # Return state, NOT session (services will create their own)

&nbsp;   return game\_state, save\_path

```



\*\*Benefits:\*\*

\-   \*\*No Dangling Sessions\*\*: Initialization is a clean, atomic operation.

\-   \*\*Clear API\*\*: Methods return only the data needed by the caller.

\-   \*\*Service Independence\*\*: Each operational service manages its own session lifecycle.

\-   \*\*Connection Pooling\*\*: Sessions return to the pool immediately, ready for use by other services.

\-   \*\*Easier Testing\*\*: Initialization can be tested as a distinct unit of work.



---



\## 2. Query/Read-Only Operations (`GameQueryService`)



\*\*Role:\*\* A unified, read-only service for fetching game data for the UI. All methods are designed to be safe, fast, and stateless.



\*\*Architecture:\*\*

This service follows a strict "session-per-query" pattern. Each method creates its own short-lived session using a `with` statement (context manager), performs its queries, converts the results to dataclasses, and automatically closes the session.



\*\*Key Principles:\*\*

1\.  \*\*Store `session\_factory`, NOT a session instance\*\*: The service itself is stateless.

2\.  \*\*Each method creates its own session\*\*: Achieved using `with self.session\_factory() as session:`.

3\.  \*\*Session is automatically closed\*\*: The context manager guarantees `session.close()` even if errors occur.

4\.  \*\*No explicit commit needed\*\*: These are read-only operations.

5\.  \*\*Convert DB models to dataclasses BEFORE session closes\*\*: This is critical to avoid `DetachedInstanceError` when accessing relationships.



\*\*Pattern Template:\*\*

```python

def query\_method(self, ...) -> List\[DataClass]:

&nbsp;   '''Single query operation.'''

&nbsp;   with self.session\_factory() as session:

&nbsp;       results = session.query(ModelDB).options(

&nbsp;           # CRITICAL: Use eager loading for relationships

&nbsp;           selectinload(ModelDB.relationship\_a),

&nbsp;           selectinload(ModelDB.relationship\_b).joinedload(RelatedDB.nested)

&nbsp;       ).filter(...).all()

&nbsp;       

&nbsp;       # Convert to dataclasses while session is still open

&nbsp;       return \[r.to\_dataclass(DataClass) for r in results]

&nbsp;   # Session auto-closed here, returns to pool

```



\### Eager Loading Pattern

Always eagerly load any relationships that will be accessed by the `to\_dataclass()` conversion method.



\-   Use `selectinload()` for one-to-many relationships (issues a separate `SELECT IN`).

\-   Use `joinedload()` for many-to-one relationships (issues a `LEFT JOIN`).

\-   Chain `joinedload()` after `selectinload()` for nested relationships.



This prevents `DetachedInstanceError` which occurs when code tries to access lazy-loaded relationships after the session that created the object has been closed.



\*\*Benefits:\*\*

\-   \*\*No Session Leaks\*\*: Automatic cleanup via the context manager is foolproof.

\-   \*\*No Shared State\*\*: Each query is isolated, preventing unintended side effects.

\-   \*\*Thread-Safe by Design\*\*: Each thread or task gets its own session from the pool.

\-   \*\*Efficient Connection Pooling\*\*: Connections are returned to the pool immediately after the query completes.



---



\## 3. Command/Write Operations (`SceneCommandService`)



\*\*Role:\*\* This service handles all write operations (create, update, delete) for a specific domain, such as scenes.



\*\*Architecture:\*\*

The service manages its own transactions for user-initiated actions. For complex, multi-step processes orchestrated by another service (like `TimeService`), its methods are designed to operate within the caller's transaction by receiving an active session as a parameter.



\*\*Key Principles:\*\*

1\.  \*\*Store `session\_factory`\*\*: The service creates sessions on demand.

2\.  \*\*Public methods create their own sessions\*\*: A method called directly from the UI (e.g., casting a talent) should manage its own complete transaction.

3\.  \*\*Always use `try/except/finally`\*\*: Ensures commit on success, rollback on error, and session closure.

4\.  \*\*Emit signals AFTER successful commit\*\*: Guarantees the UI is reacting to data that is actually persisted in the database.

5\.  \*\*Helper/Orchestrated methods receive a session from the caller\*\*: Allows multiple operations to be grouped into a single atomic transaction.



\### Pattern 1: Public Command Method (Creates Own Session)

Used for self-contained, user-initiated actions.



```python

def public\_command(self, ...) -> bool:

&nbsp;   '''User-initiated command that creates its own transaction.'''

&nbsp;   session = self.session\_factory()

&nbsp;   try:

&nbsp;       # Fetch and modify entities

&nbsp;       scene\_db = session.query(SceneDB).get(scene\_id)

&nbsp;       scene\_db.status = 'new\_status'

&nbsp;       

&nbsp;       # Call helper if needed (pass session)

&nbsp;       self.\_helper\_method(session, scene\_db)

&nbsp;       

&nbsp;       session.commit()

&nbsp;       

&nbsp;       # Emit signals AFTER commit

&nbsp;       self.signals.scenes\_changed.emit()

&nbsp;       return True

&nbsp;   except Exception as e:

&nbsp;       session.rollback()

&nbsp;       logger.error(f"Error: {e}", exc\_info=True)

&nbsp;       return False

&nbsp;   finally:

&nbsp;       session.close()

```



\### Pattern 2: Orchestrator-Called Method (Receives Session)

Used when the method is just one step in a larger process managed by an orchestrator like `TimeService`.



```python

def process\_step(self, session: Session, ...) -> bool:

&nbsp;   '''Called by TimeService during week advancement.'''

&nbsp;   # Perform operations using the passed-in session

&nbsp;   items = session.query(Model).filter(...).all()

&nbsp;   for item in items:

&nbsp;       item.field = new\_value

&nbsp;   

&nbsp;   # NO commit, NO close - the orchestrator handles it

&nbsp;   return success

```



\*\*Benefits:\*\*

\-   \*\*Transactional Integrity\*\*: User actions are atomic.

\-   \*\*Error Isolation\*\*: A failure in one command doesn't affect others.

\-   \*\*Flexibility\*\*: Methods can be called standalone or as part of a larger, orchestrated workflow.

\-   \*\*Clear Ownership\*\*: The method that creates the session is responsible for its entire lifecycle.

\-   \*\*UI Consistency\*\*: Signals are only sent after data is safely written, preventing race conditions.



---



\## 4. Orchestration Operations (`TimeService`)



\*\*Role:\*\* Orchestrates complex, multi-step state changes that must occur within a single transaction, such as advancing the game week.



\*\*Architecture:\*\*

An orchestrator service creates a single session and passes it to the various command and market service methods that perform the actual work. The orchestrator is responsible for the final `commit` or `rollback` of the entire transaction.



\*\*Pattern Description:\*\*

The `TimeService.advance\_week` method is the prime example. It:

1\.  Creates a new session from its `session\_factory`.

2\.  Calls multiple methods from other services in a specific order:

&nbsp;   -   `market\_service.recover\_all\_market\_saturation(session)`

&nbsp;   -   `scene\_command\_service.shoot\_scene(session, ...)`

&nbsp;   -   `scene\_command\_service.process\_weekly\_post\_production(session)`

&nbsp;   -   `talent\_command\_service.process\_weekly\_updates(session, ...)`

3\.  Each of these called methods receives the active session and performs its modifications without committing.

4\.  After all steps are complete, `TimeService` commits the transaction.

5\.  If any step raises an exception, the entire transaction is rolled back, ensuring the game state remains consistent.

6\.  The session is closed in a `finally` block.



\*\*Benefits:\*\*

\-   \*\*Atomicity\*\*: Complex processes like advancing a week are "all or nothing," preventing partial updates that could corrupt game state.

\-   \*\*Centralized Logic\*\*: The order of operations is clearly defined in one place.

\-   \*\*Reusability\*\*: The individual command service methods remain focused on their specific tasks and can be used in other contexts.



---



\## 5. File Operations (`SaveManager`)



\*\*Role:\*\* Manages file-level operations on the SQLite database files (copying, moving, deleting saves).



\*\*Architecture:\*\*

This service interacts with database files directly. It does not require sessions for file I/O, but it must carefully manage the `DBManager`'s connection to release file locks before performing any operations.



\*\*Key Principles:\*\*

1\.  \*\*File operations do NOT require sessions\*\*: `shutil.copyfile` works on the file path.

2\.  \*\*Disconnect from database before file operations\*\*: This is critical to release file handles and prevent `PermissionError` or "database is locked" errors, especially on Windows.

3\.  \*\*Reconnect after file operations\*\*: Restores the connection so the application can continue interacting with the database.

4\.  \*\*Use temporary sessions for metadata reading only\*\*: When loading a game, a session is created briefly just to read the `GameInfo` table, and then immediately closed.

5\.  \*\*Assume all changes are committed before calling\*\*: File operations should work on a database file that is in a consistent, committed state.



\*\*Pattern Template:\*\*

```python

def file\_operation(self):

&nbsp;   '''An operation on a database file.'''

&nbsp;   db\_path = self.db\_manager.db\_path

&nbsp;   

&nbsp;   # 1. Disconnect to release file locks

&nbsp;   self.db\_manager.disconnect()

&nbsp;   

&nbsp;   try:

&nbsp;       # 2. Perform file operations (copy, move, delete)

&nbsp;       shutil.copyfile(source, destination)

&nbsp;   finally:

&nbsp;       # 3. Reconnect for future operations

&nbsp;       self.db\_manager.connect\_to\_db(db\_path)

```



\*\*Benefits:\*\*

\-   \*\*Clear Separation\*\*: A clean distinction between database (SQL) operations and file system operations.

\-   \*\*Lock Safety\*\*: Explicitly disconnecting prevents OS-level file locking issues.

\-   \*\*Works with Session Factory\*\*: This pattern integrates perfectly with the other services. For example, `TimeService` commits and closes its session, then the `GameController` can safely call `save\_manager.auto\_save()`, which will operate on the now-unlocked, fully-committed database file.

