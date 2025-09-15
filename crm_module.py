# crm_module.py
"""
CRM functionality for the Dog Walking App
Provides customer relationship management features including:
- Communication history tracking
- Customer segmentation with tags
- Enhanced customer analytics
- Follow-up management
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class InteractionType(Enum):
    EMAIL = "email"
    PHONE = "phone"
    MEETING = "meeting"
    SERVICE_ISSUE = "service_issue"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    FOLLOW_UP = "follow_up"
    BOOKING_CHANGE = "booking_change"
    PAYMENT_ISSUE = "payment_issue"
    OTHER = "other"

class CustomerStatus(Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    CHURNED = "churned"
    VIP = "vip"

@dataclass
class CustomerInteraction:
    id: Optional[int]
    client_id: int
    interaction_type: InteractionType
    subject: str
    description: str
    interaction_date: str
    follow_up_date: Optional[str]
    status: str
    created_by: str
    created_at: str

@dataclass
class CustomerTag:
    id: Optional[int]
    name: str
    color: str
    description: str

@dataclass
class CustomerAnalytics:
    client_id: int
    total_bookings: int
    total_revenue_cents: int
    average_booking_value_cents: int
    last_booking_date: Optional[str]
    customer_lifetime_days: int
    interaction_count: int
    last_interaction_date: Optional[str]
    status: CustomerStatus

class CRMManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ensure_crm_schema()
    
    def ensure_crm_schema(self):
        """Ensure all CRM tables and columns exist"""
        cur = self.conn.cursor()
        
        # Customer interaction tracking
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                interaction_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                interaction_date TEXT NOT NULL,
                follow_up_date TEXT,
                status TEXT DEFAULT 'completed',
                created_by TEXT DEFAULT 'system',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Customer tags for segmentation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#007bff',
                description TEXT
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_tags (
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES customer_tags(id) ON DELETE CASCADE,
                assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (client_id, tag_id)
            )
        """)
        
        # Add CRM fields to existing clients table
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN status TEXT DEFAULT 'active'")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN acquisition_date TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN last_service_date TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN total_revenue_cents INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN service_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Create indexes for better performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interactions_client ON customer_interactions(client_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_interactions_date ON customer_interactions(interaction_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_tags ON client_tags(client_id)")
        
        # Insert default tags if they don't exist
        default_tags = [
            ("VIP Customer", "#ffd700", "High-value customers requiring premium service"),
            ("New Customer", "#28a745", "Recently acquired customers needing special attention"),
            ("At Risk", "#dc3545", "Customers showing signs of potential churn"),
            ("High Value", "#6f42c1", "Customers with high lifetime value"),
            ("Regular Customer", "#007bff", "Consistent, reliable customers"),
            ("Seasonal", "#fd7e14", "Customers who use services seasonally"),
            ("Referral Source", "#20c997", "Customers who refer others"),
            ("Special Needs", "#6c757d", "Pets with special care requirements")
        ]
        
        for name, color, description in default_tags:
            cur.execute("INSERT OR IGNORE INTO customer_tags (name, color, description) VALUES (?, ?, ?)",
                       (name, color, description))
        
        self.conn.commit()
    
    def add_interaction(self, client_id: int, interaction_type: InteractionType, 
                       subject: str, description: str = "", 
                       follow_up_date: Optional[str] = None,
                       created_by: str = "system") -> int:
        """Add a new customer interaction"""
        cur = self.conn.cursor()
        interaction_date = datetime.now().isoformat()
        
        cur.execute("""
            INSERT INTO customer_interactions 
            (client_id, interaction_type, subject, description, interaction_date, 
             follow_up_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_id, interaction_type.value, subject, description, 
              interaction_date, follow_up_date, created_by))
        
        self.conn.commit()
        return cur.lastrowid
    
    def get_client_interactions(self, client_id: int, limit: int = 50) -> List[CustomerInteraction]:
        """Get interaction history for a client"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM customer_interactions 
            WHERE client_id = ? 
            ORDER BY interaction_date DESC 
            LIMIT ?
        """, (client_id, limit))
        
        interactions = []
        for row in cur.fetchall():
            interactions.append(CustomerInteraction(
                id=row["id"],
                client_id=row["client_id"],
                interaction_type=InteractionType(row["interaction_type"]),
                subject=row["subject"],
                description=row["description"] or "",
                interaction_date=row["interaction_date"],
                follow_up_date=row["follow_up_date"],
                status=row["status"],
                created_by=row["created_by"],
                created_at=row["created_at"]
            ))
        return interactions
    
    def add_tag_to_client(self, client_id: int, tag_id: int) -> bool:
        """Add a tag to a client"""
        try:
            cur = self.conn.cursor()
            cur.execute("INSERT OR IGNORE INTO client_tags (client_id, tag_id) VALUES (?, ?)",
                       (client_id, tag_id))
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error:
            return False
    
    def remove_tag_from_client(self, client_id: int, tag_id: int) -> bool:
        """Remove a tag from a client"""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM client_tags WHERE client_id = ? AND tag_id = ?",
                       (client_id, tag_id))
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error:
            return False
    
    def get_client_tags(self, client_id: int) -> List[CustomerTag]:
        """Get all tags for a client"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT t.* FROM customer_tags t
            JOIN client_tags ct ON t.id = ct.tag_id
            WHERE ct.client_id = ?
            ORDER BY t.name
        """, (client_id,))
        
        tags = []
        for row in cur.fetchall():
            tags.append(CustomerTag(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                description=row["description"]
            ))
        return tags
    
    def get_all_tags(self) -> List[CustomerTag]:
        """Get all available customer tags"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM customer_tags ORDER BY name")
        
        tags = []
        for row in cur.fetchall():
            tags.append(CustomerTag(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                description=row["description"]
            ))
        return tags
    
    def create_tag(self, name: str, color: str = "#007bff", description: str = "") -> int:
        """Create a new customer tag"""
        cur = self.conn.cursor()
        cur.execute("INSERT INTO customer_tags (name, color, description) VALUES (?, ?, ?)",
                   (name, color, description))
        self.conn.commit()
        return cur.lastrowid
    
    def update_client_status(self, client_id: int, status: CustomerStatus):
        """Update a client's status"""
        cur = self.conn.cursor()
        cur.execute("UPDATE clients SET status = ? WHERE id = ?", 
                   (status.value, client_id))
        self.conn.commit()
    
    def calculate_customer_analytics(self, client_id: int) -> CustomerAnalytics:
        """Calculate analytics for a specific customer"""
        cur = self.conn.cursor()
        
        # Get basic customer info
        client_row = cur.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client_row:
            raise ValueError(f"Client {client_id} not found")
        
        # Calculate booking statistics
        booking_stats = cur.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COALESCE(SUM(price_cents), 0) as total_revenue,
                COALESCE(AVG(price_cents), 0) as avg_booking_value,
                MAX(start_dt) as last_booking
            FROM bookings 
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        
        # Calculate interaction statistics
        interaction_stats = cur.execute("""
            SELECT 
                COUNT(*) as interaction_count,
                MAX(interaction_date) as last_interaction
            FROM customer_interactions 
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        
        # Calculate customer lifetime
        acquisition_date = client_row["acquisition_date"]
        if acquisition_date:
            lifetime = (datetime.now() - datetime.fromisoformat(acquisition_date)).days
        else:
            # Use first booking as proxy for acquisition
            first_booking = cur.execute("""
                SELECT MIN(start_dt) FROM bookings WHERE client_id = ?
            """, (client_id,)).fetchone()[0]
            if first_booking:
                lifetime = (datetime.now() - datetime.fromisoformat(first_booking)).days
            else:
                lifetime = 0
        
        return CustomerAnalytics(
            client_id=client_id,
            total_bookings=booking_stats["total_bookings"],
            total_revenue_cents=booking_stats["total_revenue"],
            average_booking_value_cents=int(booking_stats["avg_booking_value"]),
            last_booking_date=booking_stats["last_booking"],
            customer_lifetime_days=lifetime,
            interaction_count=interaction_stats["interaction_count"],
            last_interaction_date=interaction_stats["last_interaction"],
            status=CustomerStatus(client_row["status"] or "active")
        )
    
    def get_clients_needing_follow_up(self, days_since_last_contact: int = 30) -> List[Tuple[int, str, str]]:
        """Get clients who haven't been contacted recently"""
        cur = self.conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days_since_last_contact)).isoformat()
        
        cur.execute("""
            SELECT DISTINCT c.id, c.name, c.email
            FROM clients c
            LEFT JOIN customer_interactions ci ON c.id = ci.client_id
            WHERE c.status = 'active'
            AND (ci.interaction_date IS NULL OR ci.interaction_date < ?)
            ORDER BY c.name
        """, (cutoff_date,))
        
        return [(row["id"], row["name"], row["email"]) for row in cur.fetchall()]
    
    def get_high_value_customers(self, min_revenue_cents: int = 50000) -> List[Tuple[int, str, int]]:
        """Get customers with high lifetime value"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, COALESCE(SUM(b.price_cents), 0) as total_revenue
            FROM clients c
            LEFT JOIN bookings b ON c.id = b.client_id
            WHERE c.status IN ('active', 'vip')
            GROUP BY c.id, c.name
            HAVING total_revenue >= ?
            ORDER BY total_revenue DESC
        """, (min_revenue_cents,))
        
        return [(row["id"], row["name"], row["total_revenue"]) for row in cur.fetchall()]
    
    def get_at_risk_customers(self, days_since_last_booking: int = 60) -> List[Tuple[int, str, str]]:
        """Identify customers at risk of churning"""
        cur = self.conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days_since_last_booking)).isoformat()
        
        cur.execute("""
            SELECT c.id, c.name, MAX(b.start_dt) as last_booking
            FROM clients c
            JOIN bookings b ON c.id = b.client_id
            WHERE c.status = 'active'
            GROUP BY c.id, c.name
            HAVING last_booking < ?
            ORDER BY last_booking ASC
        """, (cutoff_date,))
        
        return [(row["id"], row["name"], row["last_booking"]) for row in cur.fetchall()]
    
    def bulk_update_customer_stats(self):
        """Update calculated fields for all customers"""
        cur = self.conn.cursor()
        
        # Update total revenue and service count for all clients
        cur.execute("""
            UPDATE clients SET 
                total_revenue_cents = (
                    SELECT COALESCE(SUM(price_cents), 0) 
                    FROM bookings 
                    WHERE client_id = clients.id
                ),
                service_count = (
                    SELECT COUNT(*) 
                    FROM bookings 
                    WHERE client_id = clients.id
                ),
                last_service_date = (
                    SELECT MAX(start_dt) 
                    FROM bookings 
                    WHERE client_id = clients.id
                )
        """)
        
        # Set acquisition date for clients without one
        cur.execute("""
            UPDATE clients SET acquisition_date = (
                SELECT MIN(start_dt) FROM bookings WHERE client_id = clients.id
            ) WHERE acquisition_date IS NULL
        """)
        
        self.conn.commit()