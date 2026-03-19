# Component Architecture (Phase 3)

Date: 2026-03-13

## Layering
- Presentation Layer
  - Section views in `index.html`
  - UI components in `src/ui/components/*`
- Application Layer
  - `App` and page controllers/handlers
  - Workflow orchestration (prediction, simulation, schedule)
- Domain Layer
  - `PredictionEngine` and strategies
  - Data transformation in `DataProcessor`
- Infrastructure Layer
  - `ApiClient` and shared API origin resolver
  - Backend health and retry policies

## Component Boundaries (Target)
- `UploadFeature`
  - File selection, parse, validate, upload
- `HistoryFeature`
  - Draw listing, CRUD modal, pagination
- `SimulationFeature`
  - Batch run and comparison output
  - `src/core/handlers/SimulationHandler.js` (implemented extraction)
- `PredictionFeature`
  - Method selection and result rendering
  - `src/core/handlers/PredictionHandler.js` (implemented extraction)
- `SmartBettingFeature`
  - Wheeling + entropy 8-bet
- `AutoLearningFeature`
  - Optimize, schedule, sync, advanced flows

## Data Flow Rules
- UI components emit intents only.
- Feature controllers call service/api layer.
- No feature directly hardcodes API host.
- Strategy classes receive endpoint origin from shared resolver.
