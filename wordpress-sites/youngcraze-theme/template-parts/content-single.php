<?php
/**
 * Full article body for single.php.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
$yc_categories = get_the_category();
?>
<article id="post-<?php the_ID(); ?>" <?php post_class( 'single-article' ); ?>>
	<header class="single-article__header">
		<?php if ( ! empty( $yc_categories ) ) : ?>
			<a class="single-article__cat" href="<?php echo esc_url( get_category_link( $yc_categories[0]->term_id ) ); ?>">
				<?php echo esc_html( $yc_categories[0]->name ); ?>
			</a>
		<?php endif; ?>
		<h1 class="single-article__title"><?php the_title(); ?></h1>
		<div class="single-article__meta">
			<?php yc_posted_on(); ?> &middot; <?php yc_posted_by(); ?>
		</div>
	</header>

	<?php if ( has_post_thumbnail() ) : ?>
		<div class="single-article__media">
			<?php the_post_thumbnail( 'yc-featured' ); ?>
		</div>
	<?php endif; ?>

	<div class="entry-content">
		<?php
		the_content();

		wp_link_pages( array(
			'before' => '<div class="page-links">' . esc_html__( 'Pages:', 'youngcraze' ),
			'after'  => '</div>',
		) );
		?>
	</div>

	<div class="in-content-ad-slot"><?php yc_ad_slot( 'in_content' ); ?></div>

	<?php
	$yc_tags = get_the_tags();
	if ( $yc_tags ) :
		?>
		<div class="tag-list">
			<?php foreach ( $yc_tags as $yc_tag ) : ?>
				<a href="<?php echo esc_url( get_tag_link( $yc_tag->term_id ) ); ?>">#<?php echo esc_html( $yc_tag->name ); ?></a>
			<?php endforeach; ?>
		</div>
	<?php endif; ?>
</article>
