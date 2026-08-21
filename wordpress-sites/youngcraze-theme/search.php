<?php
/**
 * Search results template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();
?>
<header class="archive-header">
	<h1>
		<?php
		printf(
			/* translators: %s: search query */
			esc_html__( 'Search results for: %s', 'youngcraze' ),
			'<span>' . get_search_query() . '</span>'
		);
		?>
	</h1>
</header>

<div class="content-layout">
	<div>
		<?php if ( have_posts() ) : ?>
			<div class="post-grid">
				<?php
				while ( have_posts() ) :
					the_post();
					get_template_part( 'template-parts/content' );
				endwhile;
				?>
			</div>
			<?php yc_pagination(); ?>
		<?php else : ?>
			<?php get_template_part( 'template-parts/content', 'none' ); ?>
		<?php endif; ?>
	</div>
	<?php get_sidebar(); ?>
</div>
<?php get_footer(); ?>
