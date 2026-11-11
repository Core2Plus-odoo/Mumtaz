import { useOutletContext } from 'react-router-dom';
import { api, type Card as CardT, type Rate } from '../lib/api';
import { useT } from '../lib/i18n';
import { TopBar } from '../components/Shell';
import { Empty, ErrorBox, Loading, useLoad } from '../components/ui';

export function CardGrid({ cards }: { cards: CardT[] }) {
  const { t } = useT();
  if (!cards.length) return <Empty />;
  return (
    <div className="cards">
      {cards.map((c) => (
        <article key={c.id} className={`dcard ${c.kind}`}>
          <h4>{c.title} {c.restricted && <span className="tag gold">{t('restricted')}</span>}</h4>
          {c.detail && <p>{c.detail}</p>}
          {c.recommendation && <p className="rec">{t('recommendation')}: {c.recommendation}</p>}
          {c.impact && <p className="small muted">{t('impact')}: {c.impact}</p>}
        </article>
      ))}
    </div>
  );
}

export default function Cards() {
  const { t } = useT();
  const { rate } = useOutletContext<{ rate: Rate | null }>();
  const cards = useLoad(() => api.cards('open'));
  return (
    <>
      <TopBar title={t('cards_title')} sub={t('cards_sub')} rate={rate} />
      <div className="content">
        {cards.error && <ErrorBox error={cards.error} retry={cards.reload} />}
        {cards.loading ? <Loading /> : cards.data && <CardGrid cards={cards.data.items} />}
      </div>
    </>
  );
}
