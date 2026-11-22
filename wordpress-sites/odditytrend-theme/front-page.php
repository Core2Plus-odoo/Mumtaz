<?php
/**
 * Homepage: featured story + latest grid.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();

$ot_featured_query = new WP_Query( array(
	'posts_per_page' => 1,
	'ignore_sticky_posts' => false,
) );

$ot_featured_id = 0;
if ( $ot_featured_query->have_posts() ) {
	$ot_featured_query->the_post();
	$ot_featured_id = get_the_ID();
	?>
	<section class="featured-story">
		<?php if ( has_post_thumbnail() ) : ?>
			<a href="<?php the_permalink(); ?>" class="featured-story__media">
				<?php the_post_thumbnail( 'ot-featured' ); ?>
			</a>
		<?php endif; ?>
		<div class="featured-story__body">
			<p class="featured-story__eyebrow"><?php esc_html_e( 'Story of the Day', 'odditytrend' ); ?></p>
			<h1 class="featured-story__title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h1>
			<div class="featured-story__excerpt"><?php the_excerpt(); ?></div>
		</div>
	</section>
	<?php
}
wp_reset_postdata();
?>

<h2><?php esc_html_e( 'Latest Oddities', 'odditytrend' ); ?></h2>

<div class="content-layout">
	<div>
		<div class="post-grid">
			<?php
			$ot_latest = new WP_Query( array(
				'posts_per_page' => 9,
				'post__not_in'   => array( $ot_featured_id ),
			) );
			if ( $ot_latest->have_posts() ) :
				while ( $ot_latest->have_posts() ) :
					$ot_latest->the_post();
					get_template_part( 'template-parts/content' );
				endwhile;
			else :
				get_template_part( 'template-parts/content', 'none' );
			endif;
			wp_reset_postdata();
			?>
		</div>
	</div>
	<?php get_sidebar(); ?>
</div>

<?php get_footer(); ?>
