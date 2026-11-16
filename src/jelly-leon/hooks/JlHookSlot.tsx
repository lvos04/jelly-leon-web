/**
 * Jelly Leon: render-slot van de haakmodule (bouwplan B03 §10.11, rij "Web: menu-items": "met error boundary").
 *
 * Een upstream-scherm krijgt later één regel `<JlHookSlot name='naam' ctx={ctx} />` (eigen regel `JLW-NNNN` in
 * `docs/platform-v2/PATCHES.md`). Het slot laadt de standaardexport van de handlermodule (een React-onderdeel met de
 * prop `ctx`) met een dynamische `import()` en tekent die binnen een eigen error boundary. Mislukt de import, is de
 * naam onbekend of gooit het onderdeel een fout, dan tekent het slot niets en blijft het omliggende upstream-scherm
 * staan. Het slot toont zelf geen tekst.
 *
 * De standaardexport mag een functie- of klasse-onderdeel zijn, of een onderdeel uit `React.memo(...)` of
 * `React.forwardRef(...)` (een object met `$$typeof`). Iets anders tekent het slot niet (één consoleregel).
 *
 * Let op: React logt een fout die de boundary vangt zelf volledig op de console, met de foutmelding (in productie met
 * `console.error(fout)`, in ontwikkeling via de foutmelding van de browser). De consoleregel van het slot zelf bevat
 * alleen de haaknaam en het soort fout; de logregel van React is niet te sturen. Daarom zetten fork-onderdelen nooit
 * gegevens van de gebruiker (namen, ID's, titels uit `ctx`) in een foutmelding.
 */
import React, { Component, useEffect, useState, type ComponentType } from 'react';
import {
    JL_HOOK_HANDLERS,
    jlHookErrorKind,
    loadJlHookExport,
    logJlHookProblem,
    type JlHookContext,
    type JlHookExportCheck,
    type JlHookTable
} from './index';

export interface JlHookSlotProps {
    /** De naam van de haak in de tabel met handlers. */
    name: string;
    /** De gegevens die de upstream-plek aan het fork-onderdeel meegeeft. */
    ctx?: JlHookContext;
}

type SlotComponent = ComponentType<{ ctx: JlHookContext }>;

const LEGE_CONTEXT: JlHookContext = {};

/** De `$$typeof` van de onderdelen uit `React.memo` en `React.forwardRef` (React gebruikt `Symbol.for`). */
const REACT_WRAPPER_TYPES: readonly unknown[] = [ Symbol.for('react.memo'), Symbol.for('react.forward_ref') ];

/** Een functie- of klasse-onderdeel, of een memo- of forwardRef-onderdeel. */
function isSlotComponent(value: unknown): boolean {
    if (typeof value === 'function') {
        return true;
    }
    if (typeof value !== 'object' || value === null) {
        return false;
    }
    return REACT_WRAPPER_TYPES.indexOf((value as Record<string, unknown>).$$typeof) !== -1;
}

/** Voor het slot: de standaardexport moet een React-onderdeel zijn. */
const SLOT_EXPORT_CHECK: JlHookExportCheck = {
    accepts: isSlotComponent,
    reason: 'module heeft geen onderdeel (standaardexport is geen functie-, klasse-, memo- of forwardRef-onderdeel)'
};

function SlotLoader({ table, name, ctx }: Readonly<{ table: JlHookTable; name: string; ctx: JlHookContext }>) {
    const [loaded, setLoaded] = useState<{ name: string; component: SlotComponent } | null>(null);

    useEffect(() => {
        let active = true;
        loadJlHookExport(table, name, SLOT_EXPORT_CHECK).then(component => {
            if (active && component !== undefined) {
                setLoaded({ name, component: component as SlotComponent });
            }
        }, () => {
            // loadJlHookExport wordt nooit afgewezen; dit vangnet houdt een onverwachte afwijzing stil.
        });
        return () => {
            active = false;
        };
    }, [table, name]);

    if (!loaded || loaded.name !== name) {
        return null;
    }
    const SlotHandler = loaded.component;
    return <SlotHandler ctx={ctx} />;
}

interface BoundaryProps {
    table: JlHookTable;
    name: string;
    ctx: JlHookContext;
}

interface BoundaryState {
    failed: boolean;
}

/**
 * Eigen klasse-boundary: upstream heeft geen herbruikbare (src/components/router/ErrorBoundary.tsx is een
 * route-foutpagina) en een extra pakket zou een wijziging in package.json zijn. Bij een fout tekent hij niets.
 */
class JlHookBoundary extends Component<BoundaryProps, BoundaryState> {
    state: BoundaryState = { failed: false };

    static getDerivedStateFromError(): BoundaryState {
        return { failed: true };
    }

    componentDidCatch(error: unknown) {
        logJlHookProblem(this.props.name, `onderdeel gaf een fout (${jlHookErrorKind(error)})`);
    }

    render() {
        const { table, name, ctx } = this.props;
        return this.state.failed ? null : <SlotLoader table={table} name={name} ctx={ctx} />;
    }
}

/**
 * Maakt een render-slot bij een tabel. De fabriek bestaat voor de tests; de webclient gebruikt alleen
 * {@link JlHookSlot}.
 */
export function createJlHookSlot(table: JlHookTable) {
    function JlHookSlotForTable({ name, ctx = LEGE_CONTEXT }: Readonly<JlHookSlotProps>) {
        // key: een nieuwe naam begint met een schone boundary.
        return (
            <JlHookBoundary key={name} table={table} name={name} ctx={ctx} />
        );
    }
    return JlHookSlotForTable;
}

/** Render-slot voor fork-eigen inhoud in een upstream-scherm; tekent niets als er geen (werkende) handler is. */
export const JlHookSlot = createJlHookSlot(JL_HOOK_HANDLERS);
