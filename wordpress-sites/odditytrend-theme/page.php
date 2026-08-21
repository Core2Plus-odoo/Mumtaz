<?php
/**
 * Static page template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();
?>
<div class="content-layout">
	<div>
		<?php
		while ( have_posts() ) :
			the_post();
			?>
			<article id="post-<?php the_ID(); ?>" <?php post_class( 'single-article' ); ?>>
				<header class="single-article__header">
					<h1 class="single-article__title"><?php the_title(); ?></h1>
				</header>
				<?php if ( has_post_thumbnail() ) : ?>
					<div class="single-article__media"><?php the_post_thumbnail( 'ot-featured' ); ?></div>
				<?php endif; ?>
				<div class="entry-content"><?php the_content(); ?></div>
			</article>
			<?php
			if ( comments_open() || get_comments_number() ) :
				echo '<div class="comments-area">';
				comments_template();
				echo '</div>';
			endif;
		endwhile;
		?>
	</div>
	<?php get_sidebar(); ?>
</div>
<?php get_footer(); ?>
