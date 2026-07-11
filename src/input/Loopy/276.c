// Source: data/benchmarks/code2inv/4.c

void loopy_276(int y, int z)
{
    int x = 0;
    

    while(x < 500) {
       x += 1;
       if( z <= y) {
          y = z;
       }
    }

    {;
//@ assert(z >= y);
}

}