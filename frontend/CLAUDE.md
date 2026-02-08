# Frontend Development Guidelines

## Stack

- **Framework:** React 18
- **Language:** TypeScript
- **Build Tool:** Vite
- **Styling:** SCSS + Bootstrap 5 + react-bootstrap
- **Authentication:** Supabase
- **UI Icons:** Font Awesome

## Project Structure

```
/src/
  /components/  - React components
  /styles/      - SCSS stylesheets
  /utils/       - Utility functions
  /types/       - TypeScript type definitions
```

## Development Setup

### Environment Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   - Create `.env` file if needed
   - Add Supabase configuration
   - **Never commit `.env` to version control**

### Running Development Server

```bash
npm run dev
```

The app runs on `localhost:5173` (Vite default) or as configured.

## Code Style

### TypeScript

- **Strict typing** - Always define types, avoid `any`
- **Interfaces** - Use interfaces for object shapes
- **Type exports** - Export types from `/types/` directory
- **Type inference** - Let TypeScript infer when obvious

### React Patterns

- **Functional components** - Use function components with hooks
- **Component structure:**
  ```tsx
  // 1. Imports
  // 2. Types/Interfaces
  // 3. Component definition
  // 4. Export
  ```

- **Hooks** - Use React hooks appropriately
  - `useState` for component state
  - `useEffect` for side effects
  - `useCallback` / `useMemo` for optimization (when needed)

### Component Organization

- **Single responsibility** - One component, one purpose
- **Props interface** - Always type component props
- **Default exports** - Use default exports for components
- **File naming** - Match component name (e.g., `App.tsx` exports `App`)

### Element IDs

**CRITICAL:** Always give interactive elements meaningful `id` attributes for:
- Debugging and communication
- Testing
- Accessibility

```tsx
// Good
<button id="submit-guess-button" onClick={handleSubmit}>Submit</button>
<div id="word-grid-container">{/* ... */}</div>

// Bad
<button onClick={handleSubmit}>Submit</button>
```

## Styling

### SCSS Organization

- **Component styles** - Colocate with components when possible
- **Global styles** - Shared styles in `/styles/`
- **Bootstrap** - Use react-bootstrap components
- **Variables** - Define colors, spacing in SCSS variables
- **Responsive** - Mobile-first responsive design

### Bootstrap Usage

- **react-bootstrap** - Prefer react-bootstrap over raw Bootstrap
- **Customization** - Override Bootstrap variables in SCSS
- **Components** - Use built-in components (Button, Modal, etc.)

## State Management

### Local State

- **useState** - For component-specific state
- **Prop drilling** - Avoid deep prop drilling; lift state when needed
- **Composition** - Use component composition to pass state

### Supabase Integration

- **Authentication** - Use Supabase auth methods
- **Session management** - Handle auth state changes
- **Guest mode** - Support guest/unauthenticated users
- **API client** - Initialize Supabase client properly

## API Communication

### Backend Integration

- **Base URL** - Configure backend URL (typically `localhost:5000`)
- **Fetch/Axios** - Use consistent method for API calls
- **Error handling** - Handle network errors gracefully
- **Loading states** - Show loading indicators during API calls
- **Toast notifications** - Use react-toastify for user feedback

### API Calls Pattern

```tsx
// Example pattern
const fetchData = async () => {
  try {
    setLoading(true);
    const response = await fetch(`${API_URL}/endpoint`);
    if (!response.ok) throw new Error('API error');
    const data = await response.json();
    setData(data);
  } catch (error) {
    console.error('Error:', error);
    toast.error('Failed to load data');
  } finally {
    setLoading(false);
  }
};
```

## Game-Specific Patterns

### Word Grid

- **Grid rendering** - Dynamic grid based on backend data
- **Selection state** - Track selected words
- **Animations** - Use for submissions, reveals, errors
- **Solved state** - Display solved connections

### Submission Flow

- **Validation** - Ensure 4 words selected
- **API call** - Submit to backend
- **Response handling** - Update UI based on correct/incorrect
- **Animation phases** - Multi-phase animations for user feedback

### Game State

- **Mistakes tracking** - Display remaining attempts
- **Connections found** - Show solved connections
- **Game over** - Handle win/lose conditions

## TypeScript Best Practices

### Types Definition

```tsx
// Define interfaces for props
interface WordGridProps {
  words: string[];
  onSelect: (word: string) => void;
  selectedWords: string[];
}

// Define types for API responses
type ConnectionResponse = {
  correct: boolean;
  connection?: string;
  mistakesLeft: number;
};
```

### Type Safety

- **Props typing** - Always type component props
- **Event handlers** - Type event handlers properly
- **API responses** - Type API response data
- **Null checks** - Handle null/undefined appropriately

## Testing

### Running Tests

```bash
npm run lint  # ESLint checks
```

### Writing Tests

- **Component tests** - Test user interactions
- **Integration tests** - Test component integration
- **E2E tests** - If available, test full user flows

## Build and Deployment

### Building for Production

```bash
npm run build
```

- **Type checking** - TypeScript compiles successfully
- **Linting** - No ESLint errors
- **Preview** - Test production build with `npm run preview`

### Build Optimization

- **Code splitting** - Vite handles automatically
- **Asset optimization** - Images, fonts optimized
- **Bundle size** - Monitor bundle size

## Common Tasks

### Adding a New Component

1. Create component file in `/components/`
2. Define TypeScript interfaces for props
3. Implement component with hooks
4. Add element IDs to interactive elements
5. Add inline comments explaining logic
6. Import and use in parent component

### Styling a Component

1. Use react-bootstrap components when possible
2. Add custom SCSS in component file or `/styles/`
3. Use Bootstrap utilities for spacing/layout
4. Ensure mobile responsiveness

### Integrating a New API Endpoint

1. Define TypeScript types for request/response
2. Create API call function
3. Add loading and error states
4. Display data in component
5. Handle errors with toast notifications

### Adding Animation

1. Use CSS transitions/animations
2. Control with React state
3. Ensure smooth multi-phase animations
4. Test across different devices

## Dependencies

### Adding New Dependencies

```bash
npm install package-name
npm install -D package-name  # For dev dependencies
```

- **Justify additions** - Only add if necessary
- **Check bundle size** - Monitor impact on build size
- **Type definitions** - Install @types packages for TypeScript

## Performance

### Optimization

- **Memo components** - Use `React.memo` when beneficial
- **Callback memoization** - Use `useCallback` to prevent re-renders
- **Value memoization** - Use `useMemo` for expensive computations
- **Lazy loading** - Code-split with `React.lazy` if needed

### Avoiding Re-renders

- **State placement** - Keep state as local as possible
- **Event handlers** - Memoize with `useCallback`
- **Props comparison** - Understand when components re-render

## Accessibility

- **Semantic HTML** - Use proper HTML elements
- **ARIA labels** - Add where needed
- **Keyboard navigation** - Ensure keyboard accessibility
- **Screen readers** - Test with screen readers
- **Element IDs** - Use meaningful IDs for all interactive elements

## Debugging

### Development Tools

- **React DevTools** - Inspect component tree and state
- **Browser DevTools** - Debug JavaScript, network calls
- **TypeScript errors** - Fix type errors immediately
- **Console logging** - Use strategically, remove before commit

### Common Issues

- **State not updating** - Check state setters, useEffect dependencies
- **Props not passing** - Verify prop names and types
- **API errors** - Check network tab, backend logs
- **Styling issues** - Inspect element, check CSS specificity

## Important Reminders

- **Element IDs** - Always add IDs to interactive elements
- **TypeScript strict mode** - Keep strict typing enabled
- **Inline comments** - Write descriptive comments explaining logic
- **API contracts** - Coordinate with backend on API changes
- **Mobile testing** - Test on mobile devices/viewports
- **Supabase auth** - Handle auth state properly
- **Error boundaries** - Implement for graceful error handling
