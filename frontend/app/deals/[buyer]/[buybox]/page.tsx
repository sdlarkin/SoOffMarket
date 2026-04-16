import DealExplorer from '@/components/DealExplorer';
import { fetchDealsBuyer } from '@/lib/api';

export default async function BuyBoxDealsPage({ params }: { params: Promise<{ buyer: string; buybox: string }> }) {
    const { buyer: buyerSlug, buybox: buyboxSlug } = await params;

    // Fetch buyer/buybox names for the title
    let buyerName = buyerSlug;
    let buyboxName = buyboxSlug;
    try {
        const data = await fetchDealsBuyer(buyerSlug);
        buyerName = data.buyer.name;
        const bb = data.buyboxes.find(b => b.slug === buyboxSlug);
        if (bb) buyboxName = bb.asset_type;
    } catch (e) {
        // Fall back to slugs
    }

    return (
        <DealExplorer
            buyerSlug={buyerSlug}
            buyboxSlug={buyboxSlug}
            buyerName={buyerName}
            buyboxName={buyboxName}
        />
    );
}
