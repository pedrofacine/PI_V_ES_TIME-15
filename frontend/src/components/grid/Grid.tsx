import React from 'react';
import './Grid.css';

interface GridProps {
    children: React.ReactNode;
    className?: string;
}

export function Grid({ children, className }: GridProps) {
    return (
        <div className={`generic-grid ${className || ''}`.trim()}>
            {children}
        </div>
    );
}