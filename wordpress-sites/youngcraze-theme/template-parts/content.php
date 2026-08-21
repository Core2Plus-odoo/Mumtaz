<?php
/**
 * Post card used across the front page, archives and search results.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
$yc_categories = get_the_category();
?>
<article id="post-<?php the_ID(); ?>" <?php post_class( 'post-card' ); ?>>
	<?php if ( has_post_thumbnail() ) : ?>
		<a href="<?php the_permalink(); ?>" class="post-card__media" aria-hidden="true" tabindex="-1">
			<?php the_post_thumbnail( 'yc-card' ); ?>
		</a>
	<?php endif; ?>
	<div class="post-card__body">
		<?php if ( ! empty( $yc_categories ) ) : ?>
			<a class="post-card__cat" href="<?php echo esc_url( get_category_link( $yc_categories[0]->term_id ) ); ?>">
				<?php echo esc_html( $yc_categories[0]->name ); ?>
			</a>
		<?php endif; ?>
		<h2 class="post-card__title">
			<a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
		</h2>
		<div class="post-card__excerpt"><?php the_excerpt(); ?></div>
		<div class="post-card__meta">
			<?php echo esc_html( get_the_date() ); ?>
		</div>
	</div>
</article>
