import { useState, useEffect } from 'react'
import './App.css'

function App() {
    const [deals, setDeals] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    // Функція завантаження даних
    const fetchDeals = async () => {
        setLoading(true)
        setError(null)
        try {
            // Звертаємося до твого FastAPI
            const response = await fetch('http://127.0.0.1:8000/deals')
            if (!response.ok) {
                throw new Error('Failed to fetch from API')
            }
            let data = await response.json()
            data = data.sort((a, b) => b.profit - a.profit)
            setDeals(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    // Запускаємо при старті сторінки
    useEffect(() => {
        fetchDeals()
    }, [])

    return (
        <div className="container">
            <header>
                <h1>🔫 Skin Arbitrage Scanner</h1>
                <button onClick={fetchDeals} className="refresh-btn">
                    🔄 Refresh
                </button>
            </header>

            {loading && <p className="loading">Scanning markets...</p>}
            {error && <p className="error">Error: {error}. Is backend running?</p>}

            {!loading && !error && (
                <div className="table-container">
                    <table>
                        <thead>
                        <tr>
                            <th>Skin Name</th>
                            <th>Buy At (Skinport)</th>
                            <th>Sell At (Steam)</th>
                            <th>Profit</th>
                            <th>ROI</th>
                        </tr>
                        </thead>
                        <tbody>
                        {deals.map((deal, index) => (
                            <tr key={index}>
                                <td className="skin-name">{deal.name}</td>
                                <td>${deal.buy_at.toFixed(2)}</td>
                                <td>${deal.sell_at.toFixed(2)}</td>
                                <td className="profit">+${deal.profit.toFixed(2)}</td>
                                <td className="roi">{deal.roi}%</td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                    {deals.length === 0 && <p>No profitable deals found right now.</p>}
                </div>
            )}
        </div>
    )
}

export default App