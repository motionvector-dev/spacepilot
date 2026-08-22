import { OvenHeader } from '../components/oven/OvenHeader';
import { KanbanMatrix } from '../components/oven/KanbanMatrix';

export default function OvenAdminPage() {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface text-ink font-sans transition-colors duration-200">
      <OvenHeader />
      <KanbanMatrix />
    </div>
  );
}
