import { Link } from 'react-router'
import { Compass } from 'lucide-react'
import { Card, EmptyState } from '@/components/ui'

export default function NotFound() {
  return (
    <Card className="col-span-12">
      <EmptyState
        icon={<Compass size={18} aria-hidden />}
        title="This page doesn't exist"
        body="The link may be out of date."
        action={
          <Link to="/" className="text-xs font-semibold text-accent hover:underline">
            Go to Overview
          </Link>
        }
      />
    </Card>
  )
}
