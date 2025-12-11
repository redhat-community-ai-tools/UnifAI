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
      {toasts.map(function ({ id, title, description, action, duration, ...props }) {
        // Determine duration: use custom duration if provided, infinity for destructive, or fall back to provider default
        const toastDuration = props.variant === "destructive" ? 2147483647 : duration;
        
        return (
          <Toast
            key={id}
            {...props}
            duration={toastDuration}
            onEscapeKeyDown={(e) => e.preventDefault()}
            onSwipeEnd={(e) => e.preventDefault()}
            onClick={() => dismiss(id)}
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
