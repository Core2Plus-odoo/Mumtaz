<?php
/**
 * Homepage: trending strip + latest grid.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();

$yc_trending_query = new WP_Query( array(
	'posts_per_page' => 5,
) );
$yc_trending_ids = array();

if ( $yc_trending_query->have_posts() ) :
	?>
	<h2 class="section-title">🔥 <?php esc_html_e( 'Trending This Week', 'youngcraze' ); ?></h2>
	<div class="trending-strip">
		<?php
		$yc_rank = 0;
		while ( $yc_trending_query->have_posts() ) :
			$yc_trending_query->the_post();
			$yc_rank++;
			$yc_trending_ids[] = get_the_ID();
			?>
			<article class="trending-strip__item">
				<?php if ( has_post_thumbnail() ) : ?>
					<a href="<?php the_permalink(); ?>" class="trending-strip__media">
						<?php the_post_thumbnail( 'yc-trending' ); ?>
					</a>
				<?php endif; ?>
				<div class="trending-strip__body">
					<div class="trending-strip__rank">#<?php echo (int) $yc_rank; ?></div>
					<h3 class="trending-strip__title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h3>
				</div>
			</article>
			<?php
		endwhile;
		?>
	</div>
	<?php
endif;
wp_reset_postdata();
?>

<h2 class="section-title"><?php esc_html_e( 'Latest Explainers', 'youngcraze' ); ?></h2>

<div class="content-layout">
	<div>
		<div class="post-grid">
			<?php
			$yc_latest = new WP_Query( array(
				'posts_per_page' => 9,
				'post__not_in'   => $yc_trending_ids,
			) );
			if ( $yc_latest->have_posts() ) :
				while ( $yc_latest->have_posts() ) :
					$yc_latest->the_post();
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
