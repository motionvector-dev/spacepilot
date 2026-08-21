import { DocsSidebar } from '../components/docs/DocsSidebar';
import { DocsMainContent } from '../components/docs/DocsMainContent';

export default function DocsPage() {
  return (
    <div className="flex min-h-screen bg-black text-zinc-50 font-sans transition-colors duration-150 overflow-x-hidden">
      <DocsSidebar />
      <DocsMainContent />
    </div>
  );
}
