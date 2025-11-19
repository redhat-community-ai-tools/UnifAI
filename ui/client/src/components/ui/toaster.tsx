import { useToast } from "@/hooks/use-toast"
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast"

export function Toaster() {
  const { toasts, dismiss } = useToast()

  return (
    <ToastProvider duration={5000}>
      {toasts.map(function ({ id, title, description, action, ...props }) {
        return (
          <Toast
            key={id}
            {...props}
            duration={props.variant === "destructive" ? 2147483647 : undefined}
            onEscapeKeyDown={(e) => e.preventDefault()}
            onSwipeEnd={(e) => e.preventDefault()}
            onClick={props.variant === "destructive" ? () => dismiss(id) : undefined}
          >
            <div className="grid gap-1">
              {title && <ToastTitle className={props.variant === "destructive" ? "text-base" : undefined}>{title}</ToastTitle>}
              {description && (
                <ToastDescription className={props.variant === "destructive" ? "text-base" : undefined}>{description}</ToastDescription>
              )}
            </div>
            {action}
            {!action && <ToastClose />}
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
